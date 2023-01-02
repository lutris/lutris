"""Install a game by following its install script."""
import os
from gettext import gettext as _

from gi.repository import GLib, GObject

from lutris import settings
from lutris.config import LutrisConfig
from lutris.database.games import get_game_by_field
from lutris.installer import AUTO_EXE_PREFIX
from lutris.installer.commands import CommandsMixin
from lutris.installer.errors import MissingGameDependency, ScriptingError
from lutris.installer.installer import LutrisInstaller
from lutris.installer.legacy import get_game_launcher
from lutris.runners import InvalidRunner, NonInstallableRunnerError, RunnerInstallationError, import_runner, steam, wine
from lutris.services.lutris import download_lutris_media
from lutris.util import system
from lutris.util.display import DISPLAY_MANAGER
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import unpack_dependencies
from lutris.util.wine.wine import get_wine_version_exe


class ScriptInterpreter(GObject.Object, CommandsMixin):
    """Control the execution of an installer"""

    __gsignals__ = {
        "runners-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, installer, parent=None):
        super().__init__()
        self.target_path = None
        self.parent = parent
        self.service = parent.service if parent else None
        _appid = parent.appid if parent else None
        self.game_dir_created = False  # Whether a game folder was created during the install
        # Extra files for installers, either None if the extras haven't been checked yet.
        # Or a list of IDs of extras to be downloaded during the install
        self.extras = None
        self.game_disc = None
        self.game_files = {}
        self.cancelled = False
        self.abort_current_task = None
        self.user_inputs = []
        self.current_command = 0  # Current installer command when iterating through them
        self.runners_to_install = []
        self.current_resolution = DISPLAY_MANAGER.get_current_resolution()
        self.installer = LutrisInstaller(installer, self, service=self.service, appid=_appid)

        if not self.installer.script:
            raise ScriptingError(_("This installer doesn't have a 'script' section"))
        script_errors = self.installer.get_errors()
        if script_errors:
            raise ScriptingError(
                _("Invalid script: \n{}").format("\n".join(script_errors)), self.installer.script
            )

        self._check_binary_dependencies()
        self._check_dependency()
        if self.installer.creates_game_folder:
            self.target_path = self.get_default_target()

        # Run variable substitution on the URLs
        for file in self.installer.files:
            file.set_url(self._substitute(file.url))

    @property
    def appid(self):
        logger.warning("Do not access appid from interpreter")
        return self.installer.service_appid

    def get_default_target(self):
        """Return default installation dir"""
        config = LutrisConfig(runner_slug=self.installer.runner)
        games_dir = config.system_config.get("game_path", os.path.expanduser("~"))
        if self.service:
            service_dir = self.service.id
        else:
            service_dir = ""
        return os.path.expanduser(os.path.join(games_dir, service_dir, self.installer.game_slug))

    @property
    def cache_path(self):
        """Return the directory used as a cache for the duration of the installation"""
        return os.path.join(settings.CACHE_DIR, "installer/%s" % self.installer.game_slug)

    @property
    def script_env(self):
        """Return the script's own environment variable with values
        susbtituted. This value can be used to provide the same environment
        variable as set for the game during the install process.
        """
        return {
            key: self._substitute(value) for key, value in
            self.installer.script.get('system', {}).get('env', {}).items()
        }

    @staticmethod
    def _get_game_dependency(dependency):
        """Return a game database row from a dependency name"""
        game = get_game_by_field(dependency, field="installer_slug")
        if not game:
            game = get_game_by_field(dependency, "slug")

        # Game must be installed and have a directory
        # set so we can use that as the destination
        if game and game["installed"] and game["directory"]:
            return game

    def _check_binary_dependencies(self):
        """Check if all required binaries are installed on the system.

        This reads a `require-binaries` entry in the script, parsed the same way as
        the `requires` entry.
        """
        binary_dependencies = unpack_dependencies(self.installer.script.get("require-binaries"))
        for dependency in binary_dependencies:
            if isinstance(dependency, tuple):
                installed_binaries = {
                    dependency_option: bool(system.find_executable(dependency_option))
                    for dependency_option in dependency
                }
                if not any(installed_binaries.values()):
                    raise ScriptingError(_("This installer requires %s on your system") % _(" or ").join(dependency))
            else:
                if not system.find_executable(dependency):
                    raise ScriptingError(_("This installer requires %s on your system") % dependency)

    def _check_dependency(self):
        """When a game is a mod or an extension of another game, check that the base
        game is installed.
        If the game is available, install the game in the base game folder.
        The first game available listed in the dependencies is the one picked to base
        the installed on.
        """
        if self.installer.extends:
            dependencies = [self.installer.extends]
        else:
            dependencies = unpack_dependencies(self.installer.requires)
        error_message = _("You need to install {} before")
        for index, dependency in enumerate(dependencies):
            if isinstance(dependency, tuple):
                installed_games = [dep for dep in [self._get_game_dependency(dep) for dep in dependency] if dep]
                if not installed_games:
                    if len(dependency) == 1:
                        raise MissingGameDependency(slug=dependency)
                    raise ScriptingError(error_message.format(_(" or ").join(dependency)))
                if index == 0:
                    self.target_path = installed_games[0]["directory"]
                    self.requires = installed_games[0]["installer_slug"]
            else:
                game = self._get_game_dependency(dependency)
                if not game:
                    raise MissingGameDependency(slug=dependency)
                if index == 0:
                    self.target_path = game["directory"]
                    self.requires = game["installer_slug"]

    def get_extras(self):
        """Get extras and store them to move them at the end of the install"""
        if not self.service or not self.service.has_extras:
            self.extras = []
            return self.extras
        self.extras = self.service.get_extras(self.installer.service_appid)
        return self.extras

    def launch_install(self, ui_delegate):
        """Launch the install process; returns False if cancelled by the user."""
        self.runners_to_install = self.get_runners_to_install()

        if self.installer.runner.startswith("wine"):
            if not ui_delegate.check_wine_availability():
                return False

        self.install_runners(ui_delegate)
        self.create_game_folder()
        return True

    def create_game_folder(self):
        """Create the game folder if needed and store if is was created"""
        if (
                self.installer.files
                and self.target_path
                and not system.path_exists(self.target_path)
                and self.installer.creates_game_folder
        ):
            try:
                logger.debug("Creating destination path %s", self.target_path)
                os.makedirs(self.target_path)
                self.game_dir_created = True
            except PermissionError as err:
                raise ScriptingError(
                    _("Lutris does not have the necessary permissions to install to path:"),
                    self.target_path,
                ) from err

    def get_runners_to_install(self):
        """Check if the runner is installed before starting the installation
        Install the required runner(s) if necessary. This should handle runner
        dependencies or runners used for installer tasks.
        """
        runners_to_install = []
        required_runners = []
        runner = self.get_runner_class(self.installer.runner)
        required_runners.append(runner())

        for command in self.installer.script.get("installer", []):
            command_name, command_params = self._get_command_name_and_params(command)
            if command_name == "task":
                runner_name, _task_name = self._get_task_runner_and_name(command_params["name"])
                runner_names = [r.name for r in required_runners]
                if runner_name not in runner_names:
                    required_runners.append(self.get_runner_class(runner_name)())

        for runner in required_runners:
            params = {}
            if self.installer.runner == "libretro":
                params["core"] = self.installer.script["game"]["core"]
            if self.installer.runner.startswith("wine"):
                # Force the wine version to be installed
                params["fallback"] = False
                params["min_version"] = wine.MIN_SAFE_VERSION
                version = self._get_runner_version()
                if version:
                    params["version"] = version
                else:
                    # Looking up default wine version
                    default_wine = runner.get_runner_version() or {}
                    if "version" in default_wine:
                        logger.debug("Default wine version is %s", default_wine["version"])
                        # Set the version to both the is_installed params and
                        # the script itself so the version gets saved at the
                        # end of the install.
                        if self.installer.runner not in self.installer.script:
                            self.installer.script[self.installer.runner] = {}
                        version = "{}-{}".format(default_wine["version"],
                                                 default_wine["architecture"])
                        params["version"] = \
                            self.installer.script[self.installer.runner]["version"] = version
                    else:
                        logger.error("Failed to get default wine version (got %s)", default_wine)

            if not runner.is_installed(**params):
                logger.info("Runner %s needs to be installed", runner)
                runners_to_install.append(runner)

        return runners_to_install

    def install_runners(self, ui_delegate):
        """Install required runners for a game"""
        if self.runners_to_install:
            self.install_runner(self.runners_to_install.pop(0), ui_delegate)
            return
        self.emit("runners-installed")

    def install_runner(self, runner, ui_delegate):
        """Install runner required by the install script"""
        def install_more_runners():
            self.install_runners(ui_delegate)

        logger.debug("Installing %s", runner.name)
        try:
            runner.install(
                ui_delegate,
                version=self._get_runner_version(),
                callback=install_more_runners,
            )
        except (NonInstallableRunnerError, RunnerInstallationError) as ex:
            logger.error(ex.message)
            raise ScriptingError(ex.message) from ex

    def get_runner_class(self, runner_name):
        """Runner the runner class from its name"""
        try:
            runner = import_runner(runner_name)
        except InvalidRunner as err:
            GLib.idle_add(self.parent.cancel_button.set_sensitive, True)
            raise ScriptingError(_("Invalid runner provided %s") % runner_name) from err
        return runner

    def launch_installer_commands(self):
        """Run the pre-installation steps and launch install."""
        if self.target_path and os.path.exists(self.target_path):
            os.chdir(self.target_path)
        os.makedirs(self.cache_path, exist_ok=True)

        # Copy extras to game folder
        if len(self.extras) and len(self.extras) == len(self.installer.files):
            # Reset the install script in case there are only extras.
            logger.warning("Installer with only extras and no game files")
            self.installer.script["installer"] = []

        for extra in self.extras:
            self.installer.script["installer"].append(
                {"copy": {"src": extra, "dst": "$GAMEDIR/extras"}}
            )
        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):

        if result == "STOP" or self.cancelled:
            return

        self.parent.present_spinner_page()
        self.parent.continue_button.hide()

        commands = self.installer.script.get("installer", [])
        if exception:
            logger.error("Last install command failed, show error")
            self.parent.show_install_error_message(repr(exception))
        elif self.current_command < len(commands):
            try:
                command = commands[self.current_command]
            except KeyError as err:
                raise ScriptingError(_("Installer commands are not formatted correctly")) from err
            self.current_command += 1
            method, params = self._map_command(command)
            if isinstance(params, dict):
                status_text = params.pop("description", None)
            else:
                status_text = None
            if status_text:
                self.parent.set_status(status_text)
            logger.debug("Installer command: %s", command)
            AsyncCall(method, self._iter_commands, params)
        else:
            logger.debug("Commands %d out of %s completed", self.current_command, len(commands))
            self._finish_install()

    @staticmethod
    def _get_command_name_and_params(command_data):
        if isinstance(command_data, dict):
            command_name = list(command_data.keys())[0]
            command_params = command_data[command_name]
        else:
            command_name = command_data
            command_params = {}
        command_name = command_name.replace("-", "_")
        # Prevent private methods from being accessed as commands
        command_name = command_name.strip("_")
        return command_name, command_params

    def _map_command(self, command_data):
        """Map a directive from the `installer` section to an internal
        method."""
        command_name, command_params = self._get_command_name_and_params(command_data)
        if not hasattr(self, command_name):
            raise ScriptingError(_('The command "%s" does not exist.') % command_name)
        return getattr(self, command_name), command_params

    def _finish_install(self):
        game_id = self.installer.save()

        launcher_value = None
        path = None
        _launcher, launcher_value = get_game_launcher(self.installer.script)
        if launcher_value:
            path = self._substitute(launcher_value)
            if not os.path.isabs(path) and self.target_path:
                path = os.path.join(self.target_path, path)
        if (
                path
                and AUTO_EXE_PREFIX not in path
                and not os.path.isfile(path)
                and self.installer.runner not in ("web", "browser")
        ):
            status = _(
                "The executable at path %s can't be found, please check the destination folder.\n"
                "Some parts of the installation process may have not completed successfully."
            ) % path
            logger.warning("No executable found at specified location %s", path)
        else:
            status = (self.installer.script.get("install_complete_text") or _("Installation completed!"))
        download_lutris_media(self.installer.game_slug)
        self.parent.finish_install(game_id, status)

    def cleanup(self):
        """Clean up install dir after a successful install"""
        os.chdir(os.path.expanduser("~"))
        system.remove_folder(self.cache_path)

    def revert(self, remove_game_dir=True):
        """Revert installation in case of an error"""
        logger.info("Cancelling installation of %s", self.installer.game_name)
        if self.installer.runner.startswith("wine"):
            self.task({"name": "winekill"})

        self.cancelled = True

        if self.abort_current_task:
            self.abort_current_task()

        if self.target_path and remove_game_dir:
            system.remove_folder(self.target_path)

    def _get_string_replacements(self):
        """Return a mapping of variables to their actual value"""
        replacements = {
            "GAMEDIR": self.target_path,
            "CACHE": self.cache_path,
            "HOME": os.path.expanduser("~"),
            "STEAM_DATA_DIR": steam.steam().steam_data_dir,
            "DISC": self.game_disc,
            "USER": os.getenv("USER"),
            "INPUT": self.user_inputs[-1]["value"] if self.user_inputs else "",
            "VERSION": self.installer.version,
            "RESOLUTION": "x".join(self.current_resolution),
            "RESOLUTION_WIDTH": self.current_resolution[0],
            "RESOLUTION_HEIGHT": self.current_resolution[1],
            "RESOLUTION_WIDTH_HEX": hex(int(self.current_resolution[0])),
            "RESOLUTION_HEIGHT_HEX": hex(int(self.current_resolution[1])),
            "WINEBIN": self.get_wine_path(),
        }
        replacements.update(self.installer.variables)
        # Add 'INPUT_<id>' replacements for user inputs with an id
        for input_data in self.user_inputs:
            alias = input_data["alias"]
            if alias:
                replacements[alias] = input_data["value"]
        replacements.update(self.game_files)
        return replacements

    def _substitute(self, template_string):
        """Replace path aliases with real paths."""
        if template_string is None:
            logger.warning("No template string given")
            return ""
        if str(template_string).replace("-", "_") in self.game_files:
            template_string = template_string.replace("-", "_")
        return system.substitute(template_string, self._get_string_replacements())

    def eject_wine_disc(self):
        """Use Wine to eject a CD, otherwise Wine can have problems detecting disc changes"""
        wine_path = get_wine_version_exe(self._get_runner_version())
        wine.eject_disc(wine_path, self.target_path)
