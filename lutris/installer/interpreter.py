"""Install a game by following its install script."""

import os
from gettext import gettext as _

from gi.repository import GObject

from lutris import settings
from lutris.config import LutrisConfig
from lutris.database.games import get_game_by_field
from lutris.exceptions import AuthenticationError, MisconfigurationError, UnavailableGameError
from lutris.gui.dialogs.delegates import Delegate
from lutris.installer import AUTO_EXE_PREFIX
from lutris.installer.commands import CommandsMixin
from lutris.installer.errors import MissingGameDependencyError, ScriptingError
from lutris.installer.installer import LutrisInstaller
from lutris.runners import NonInstallableRunnerError, RunnerInstallationError, steam, wine
from lutris.services.lutris import download_lutris_media
from lutris.util import system
from lutris.util.display import DISPLAY_MANAGER
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import unpack_dependencies


class ScriptInterpreter(GObject.Object, CommandsMixin):
    """Control the execution of an installer"""

    __gsignals__ = {
        "runners-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    class InterpreterUIDelegate(Delegate):
        """This is a base class for objects that provide UI services
        for running scripts. The InstallerWindow inherits from this."""

        def __init__(self, service=None, appid=None):
            self.service = service
            self.appid = appid

        def report_error(self, error):
            """Called to report an error during installation. The installation will then stop."""
            pass

        def report_status(self, status):
            """Called to report the current activity of the installer."""

        def attach_log(self, command):
            """Called to attach the command to a log UI, so its log output can be viewed."""

        def begin_disc_prompt(self, message, requires, installer, callback):
            """Called to prompt for a disc. When the disc is provided, the callback is invoked.
            The method returns immediately, however."""
            raise NotImplementedError()

        def begin_input_menu(self, alias, options, preselect, callback):
            """Called to prompt the user to select among a list of options. When the user
            does so, the callback is invoked. The method returns immediately, however."""
            raise NotImplementedError()

        def report_finished(self, game_id, status):
            """Called to report the successful completion of the installation."""
            logger.info("Installation of game %s completed.", game_id)

    def __init__(self, installer, interpreter_ui_delegate=None):
        super().__init__()
        self.target_path = None
        self.interpreter_ui_delegate = interpreter_ui_delegate or ScriptInterpreter.InterpreterUIDelegate()
        self.service = self.interpreter_ui_delegate.service
        _appid = self.interpreter_ui_delegate.appid
        self.game_dir_created = False  # Whether a game folder was created during the install
        # Extra files for installers, either None if the extras haven't been checked yet.
        # Or a list of IDs of extras to be downloaded during the install
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
        if not self.service and self.installer.service:
            self.service = self.installer.service
        script_errors = self.installer.get_errors()
        if script_errors:
            raise ScriptingError(
                _("Invalid script: \n{}").format("\n".join(script_errors)), faulty_data=self.installer.script
            )

        self._check_binary_dependencies()
        self._check_dependency()
        if self.installer.creates_game_folder:
            self.target_path = self.get_default_target()

    def on_timeout_error(self, error):
        self.interpreter_ui_delegate.report_error(error)

    def on_idle_error(self, error):
        self.interpreter_ui_delegate.report_error(error)

    def on_signal_error(self, error):
        self.interpreter_ui_delegate.report_error(error)

    def on_emission_hook_error(self, error):
        self.interpreter_ui_delegate.report_error(error)

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
        return os.path.join(settings.INSTALLER_CACHE_DIR, "%s" % self.installer.game_slug)

    @property
    def script_env(self):
        """Return the script's own environment variable with values
        susbtituted. This value can be used to provide the same environment
        variable as set for the game during the install process.
        """
        return {
            key: self._substitute(value)
            for key, value in self.installer.script.get("system", {}).get("env", {}).items()
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
                    dependency_option: system.can_find_executable(dependency_option) for dependency_option in dependency
                }
                if not any(installed_binaries.values()):
                    raise ScriptingError(_("This installer requires %s on your system") % _(" or ").join(dependency))
            else:
                if not system.can_find_executable(dependency):
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
                        raise MissingGameDependencyError(slug=dependency)
                    raise ScriptingError(error_message.format(_(" or ").join(dependency)))
                if index == 0:
                    self.target_path = installed_games[0]["directory"]
                    self.requires = installed_games[0]["installer_slug"]
            else:
                game = self._get_game_dependency(dependency)
                if not game:
                    raise MissingGameDependencyError(slug=dependency)
                if index == 0:
                    self.target_path = game["directory"]
                    self.requires = game["installer_slug"]

    def get_extras(self):
        """Get extras and store them to move them at the end of the install"""
        if not self.service or not self.service.has_extras or not self.installer.service_appid:
            return []
        try:
            return self.service.get_extras(self.installer.service_appid)
        except (AuthenticationError, UnavailableGameError) as ex:
            logger.exception("Unable to download list of extras: %s", ex)
            return []

    def launch_install(self, ui_delegate):
        """Launch the install process; returns False if cancelled by the user."""
        self.runners_to_install = self.get_runners_to_install()
        self.install_runners(ui_delegate)
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
                    faulty_data=self.target_path,
                ) from err
            except FileNotFoundError as err:
                raise ScriptingError(
                    _("Path %s not found, unable to create game folder. Is the disk mounted?"),
                    faulty_data=self.target_path,
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
            if not runner.is_installed_for(self):
                logger.info("Runner %s needs to be installed", runner.name)
                runners_to_install.append(runner)

        return runners_to_install

    def install_runners(self, ui_delegate):
        """Install required runners for a game"""
        if self.runners_to_install:
            self.install_runner(self.runners_to_install.pop(0), ui_delegate)
            return  # install_runner calls back into this method to get the next one

        self.emit("runners-installed")

    def install_runner(self, runner, ui_delegate):
        """Install runner required by the install script"""

        def install_more_runners():
            self.install_runners(ui_delegate)

        logger.debug("Installing %s", runner.name)
        try:
            runner.install(
                ui_delegate,
                version=runner.get_installer_runner_version(self.installer),
                callback=install_more_runners,
            )
        except (NonInstallableRunnerError, RunnerInstallationError) as ex:
            logger.error(ex.message)
            raise ScriptingError.wrap(ex) from ex

    def launch_installer_commands(self):
        """Run the pre-installation steps and launch install."""
        self.create_game_folder()

        os.makedirs(self.cache_path, exist_ok=True)

        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):
        if result == "STOP" or self.cancelled:
            return

        try:
            commands = self.installer.script.get("installer", [])
            if exception:
                logger.error("Last install command failed, show error")
                self.interpreter_ui_delegate.report_error(exception)
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
                    self.interpreter_ui_delegate.report_status(status_text)
                logger.debug("Installer command: %s", command)

                if self.target_path and os.path.exists(self.target_path):
                    # Establish a CWD for the command, but remove it afterwards
                    # for safety. We'd better not rely on this, many tasks can be
                    # fiddling with the CWD at the same time.
                    def dispatch():
                        prev_cwd = os.getcwd()
                        os.chdir(self.target_path)
                        try:
                            return method(params)
                        finally:
                            os.chdir(prev_cwd)

                    AsyncCall(dispatch, self._iter_commands)
                else:
                    AsyncCall(method, self._iter_commands, params)
            else:
                logger.debug("Commands %d out of %s completed", self.current_command, len(commands))
                self._finish_install()
        except Exception as ex:
            # Redirect errors to the delegate, instead of the default ErrorDialog.
            logger.exception("Error during installation: %s", ex)
            self.interpreter_ui_delegate.report_error(ex)

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
        path = None

        if path and AUTO_EXE_PREFIX not in path and not os.path.isfile(path) and self.installer.runner != "web":
            status = (
                _(
                    "The executable at path %s can't be found, please check the destination folder.\n"
                    "Some parts of the installation process may have not completed successfully."
                )
                % path
            )
            logger.warning("No executable found at specified location %s", path)
        else:
            status = self.installer.script.get("install_complete_text") or _("Installation completed!")
        AsyncCall(download_lutris_media, None, self.installer.game_slug)
        self.interpreter_ui_delegate.report_finished(game_id, status)

    def cleanup(self):
        """Clean up install dir after a successful install"""
        os.chdir(os.path.expanduser("~"))
        system.delete_folder(self.cache_path)

    def revert(self, remove_game_dir=True, completion_function=None, error_function=None):
        """Revert installation in case of an error. Since winekill can be slow,
        this runs asynchronously and calls cocompletion_function() when successful,
        or error_function(err) if it fails."""
        logger.info("Cancelling installation of %s", self.installer.game_name)

        self.cancelled = True

        def on_complete(_result, error):
            if error:
                error_function(error)
                return

            try:
                if self.abort_current_task:
                    self.abort_current_task()

                if self.target_path and remove_game_dir:
                    system.remove_folder(self.target_path)

                completion_function()
            except Exception as ex:
                error_function(ex)

        if self.installer.runner.startswith("wine"):
            AsyncCall(self.task, on_complete, {"name": "winekill"})
        else:
            on_complete(None, None)

    def _get_string_replacements(self):
        """Return a mapping of variables to their actual value"""

        current_res = self.current_resolution

        replacements = {
            "GAMEDIR": self.target_path,
            "CACHE": self.cache_path,
            "HOME": os.path.expanduser("~"),
            "STEAM_DATA_DIR": steam.steam().steam_data_dir,
            "DISC": self.game_disc,
            "USER": os.getenv("USER"),
            "INPUT": self.user_inputs[-1]["value"] if self.user_inputs else "",
            "VERSION": self.installer.version,
            "RESOLUTION": "x".join(current_res),
            "RESOLUTION_WIDTH": current_res[0],
            "RESOLUTION_HEIGHT": current_res[1],
        }

        try:
            replacements["RESOLUTION_WIDTH_HEX"] = hex(int(current_res[0]))
            replacements["RESOLUTION_HEIGHT_HEX"] = hex(int(current_res[1]))
        except (ValueError, TypeError):
            pass  # If we can't generate hex, just omit the vars

        try:
            replacements["WINEBIN"] = self.get_wine_path()
        except MisconfigurationError:
            pass  # If we can't get the path, just omit it

        # None values stringify as 'None', which is not what you want, so we'll
        # remove then pre-emptively. This happens for game install scripts that have
        # no 'self.target_path'.

        for key in [key for key, value in replacements.items() if value is None]:
            del replacements[key]

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
        wine_path = self.get_wine_path()
        wine.eject_disc(wine_path, self.target_path)
