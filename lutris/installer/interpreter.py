"""Install a game by following its install script."""
import os
from gettext import gettext as _

from gi.repository import GLib, GObject

from lutris import settings
from lutris.config import LutrisConfig
from lutris.database.games import get_game_by_field
from lutris.gui.dialogs import WineNotInstalledWarning
from lutris.gui.dialogs.download import simple_downloader
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
from lutris.util.wine.wine import get_system_wine_version, get_wine_version_exe


class ScriptInterpreter(GObject.Object, CommandsMixin):
    """Control the execution of an installer"""

    __gsignals__ = {
        "runners-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, installer, parent):
        super().__init__()
        self.target_path = None
        self.parent = parent
        self.service = parent.service if parent else None
        self.appid = parent.appid if parent else None
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
        self.installer = LutrisInstaller(installer, self, service=self.service, appid=self.appid)
        if not self.installer.script:
            raise ScriptingError("This installer doesn't have a 'script' section")
        script_errors = self.installer.get_errors()
        if script_errors:
            raise ScriptingError(
                "Invalid script: \n{}".format("\n".join(script_errors)), self.installer.script
            )

        self.current_resolution = DISPLAY_MANAGER.get_current_resolution()
        self._check_binary_dependencies()
        self._check_dependency()
        if self.installer.creates_game_folder:
            self.target_path = self.get_default_target()

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

    # --------------------------
    # "Initial validation" stage
    # --------------------------

    @staticmethod
    def _get_installed_dependency(dependency):
        """Return whether a dependency is installed"""
        game = get_game_by_field(dependency, field="installer_slug")

        if not game:
            game = get_game_by_field(dependency, "slug")
        if bool(game) and bool(game["directory"]):
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
                    raise ScriptingError("This installer requires %s on your system" % " or ".join(dependency))
            else:
                if not system.find_executable(dependency):
                    raise ScriptingError("This installer requires %s on your system" % dependency)

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
        error_message = "You need to install {} before"
        for index, dependency in enumerate(dependencies):
            if isinstance(dependency, tuple):
                installed_games = [dep for dep in [self._get_installed_dependency(dep) for dep in dependency] if dep]
                if not installed_games:
                    if len(dependency) == 1:
                        raise MissingGameDependency(slug=dependency)
                    raise ScriptingError(error_message.format(" or ".join(dependency)))
                if index == 0:
                    self.target_path = installed_games[0]["directory"]
                    self.requires = installed_games[0]["installer_slug"]
            else:
                game = self._get_installed_dependency(dependency)
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
        self.extras = self.service.get_extras(self.appid)
        return self.extras

    def launch_install(self):
        """Launch the install process"""
        self.runners_to_install = self.get_runners_to_install()
        self.install_runners()
        self.create_game_folder()

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
            except PermissionError:
                raise ScriptingError(
                    "Lutris does not have the necessary permissions to install to path:",
                    self.target_path,
                )

    def get_runners_to_install(self):
        """Check if the runner is installed before starting the installation
        Install the required runner(s) if necessary. This should handle runner
        dependencies (wine for winesteam) or runners used for installer tasks.
        """
        runners_to_install = []
        required_runners = []
        runner = self.get_runner_class(self.installer.runner)
        if runner.depends_on is not None:
            required_runners.append(runner.depends_on())
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

        if self.installer.runner.startswith("wine") and not get_system_wine_version():
            WineNotInstalledWarning(parent=self.parent)
        return runners_to_install

    def install_runners(self):
        """Install required runners for a game"""
        if self.runners_to_install:
            self.install_runner(self.runners_to_install.pop(0))
            return
        self.emit("runners-installed")

    def install_runner(self, runner):
        """Install runner required by the install script"""
        logger.debug("Installing %s", runner.name)
        try:
            runner.install(
                version=self._get_runner_version(),
                downloader=simple_downloader,
                callback=self.install_runners,
            )
        except (NonInstallableRunnerError, RunnerInstallationError) as ex:
            logger.error(ex.message)
            raise ScriptingError(ex.message)

    def get_runner_class(self, runner_name):
        """Runner the runner class from its name"""
        try:
            runner = import_runner(runner_name)
        except InvalidRunner:
            GLib.idle_add(self.parent.cancel_button.set_sensitive, True)
            raise ScriptingError("Invalid runner provided %s" % runner_name)
        return runner

    def launch_installer_commands(self):
        """Run the pre-installation steps and launch install."""
        if self.target_path and os.path.exists(self.target_path):
            os.chdir(self.target_path)
        if not os.path.exists(self.cache_path):
            os.mkdir(self.cache_path)

        # Copy extras to game folder
        for extra in self.extras:
            self.installer.script["installer"].append(
                {"copy": {"src": extra, "dst": "$GAMEDIR/extras"}}
            )
        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):
        if result == "STOP" or self.cancelled:
            return

        self.parent.set_status(_("Installing game data"))
        self.parent.add_spinner()
        self.parent.continue_button.hide()

        commands = self.installer.script.get("installer", [])
        if exception:
            self.parent.on_install_error(repr(exception))
        elif self.current_command < len(commands):
            try:
                command = commands[self.current_command]
            except KeyError:
                raise ScriptingError("Installer commands are not formatted correctly")
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
        command_name = command_name.strip("_")
        return command_name, command_params

    def _map_command(self, command_data):
        """Map a directive from the `installer` section to an internal
        method."""
        command_name, command_params = self._get_command_name_and_params(command_data)
        if not hasattr(self, command_name):
            raise ScriptingError('The command "%s" does not exist.' % command_name)
        return getattr(self, command_name), command_params

    def _finish_install(self):
        game = self.installer.script.get("game")
        launcher_value = None
        if game:
            _launcher, launcher_value = get_game_launcher(self.installer.script)
        path = None
        if launcher_value:
            path = self._substitute(launcher_value)
            if not os.path.isabs(path) and self.target_path:
                path = os.path.join(self.target_path, path)
        self.installer.save()
        if path and not os.path.isfile(path) and self.installer.runner not in ("web", "browser"):
            self.parent.set_status(
                _(
                    "The executable at path %s can't be found, please check the destination folder.\n"
                    "Some parts of the installation process may have not completed successfully."
                ) % path
            )
            logger.warning("No executable found at specified location %s", path)
        else:
            install_complete_text = (self.installer.script.get("install_complete_text") or _("Installation completed!"))
            self.parent.set_status(install_complete_text)
        download_lutris_media(self.installer.game_slug)
        self.parent.on_install_finished()

    def cleanup(self):
        """Clean up install dir after a successful install"""
        os.chdir(os.path.expanduser("~"))
        system.remove_folder(self.cache_path)

    def revert(self):
        """Revert installation in case of an error"""
        logger.info("Cancelling installation of %s", self.installer.game_name)
        if self.installer.runner.startswith("wine"):
            self.task({"name": "winekill"})

        self.cancelled = True

        if self.abort_current_task:
            self.abort_current_task()

        if self.game_dir_created:
            system.remove_folder(self.target_path)

    def _substitute(self, template_string):
        """Replace path aliases with real paths."""
        if not template_string:
            logger.warning("No template string given")
            return ""
        replacements = {
            "GAMEDIR": self.target_path,
            "CACHE": self.cache_path,
            "HOME": os.path.expanduser("~"),
            "STEAM_DATA_DIR": steam.steam().steam_data_dir,
            "DISC": self.game_disc,
            "USER": os.getenv("USER"),
            "INPUT": self._get_last_user_input(),
            "VERSION": self.installer.version,
            "RESOLUTION": "x".join(self.current_resolution),
            "RESOLUTION_WIDTH": self.current_resolution[0],
            "RESOLUTION_HEIGHT": self.current_resolution[1],
        }
        # Add 'INPUT_<id>' replacements for user inputs with an id
        for input_data in self.user_inputs:
            alias = input_data["alias"]
            if alias:
                replacements[alias] = input_data["value"]
        replacements.update(self.game_files)
        if str(template_string).replace("-", "_") in self.game_files:
            template_string = template_string.replace("-", "_")
        return system.substitute(template_string, replacements)

    def _get_last_user_input(self):
        return self.user_inputs[-1]["value"] if self.user_inputs else ""

    def eject_wine_disc(self):
        """Use Wine to eject a CD, otherwise Wine can have problems detecting disc changes"""
        wine_path = get_wine_version_exe(self._get_runner_version())
        wine.eject_disc(wine_path, self.target_path)
