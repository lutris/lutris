# pylint: disable=E1101, E0611
"""Install a game by following its install script."""
import os
import time
import json
import yaml

from gi.repository import GLib

from lutris import pga
from lutris import settings
from lutris.game import Game
from lutris.gui.dialogs import WineNotInstalledWarning
from lutris.util import system
from lutris.util.strings import unpack_dependencies
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.steam.log import get_app_state_log
from lutris.util.http import Request
from lutris.util.wine.wine import get_wine_version_exe, get_system_wine_version

from lutris.config import LutrisConfig, make_game_config_id

from lutris.installer.errors import ScriptingError
from lutris.installer.commands import CommandsMixin

from lutris.services.gog import (
    connect as connect_gog,
    GogService,
)

from lutris.runners import (
    wine,
    winesteam,
    steam,
    import_runner,
    InvalidRunner,
    NonInstallableRunnerError,
    RunnerInstallationError,
)


def fetch_script(game_slug, revision=None):
    """Download install script(s) for matching game_slug."""
    if revision:
        installer_url = settings.INSTALLER_REVISION_URL % (game_slug, revision)
        key = None
    else:
        installer_url = settings.INSTALLER_URL % game_slug
        key = "results"
    logger.debug("Fetching installer %s", installer_url)
    request = Request(installer_url)
    request.get()
    response = request.json
    if response is None:
        raise RuntimeError("Couldn't get installer at %s" % installer_url)

    if key:
        return response[key]
    return response


def read_script(filename):
    """Return scripts from a local file"""
    logger.debug("Loading script(s) from %s", filename)
    scripts = yaml.safe_load(open(filename, "r").read())
    if isinstance(scripts, list):
        return scripts
    if "results" in scripts:
        return scripts["results"]
    return scripts


def _get_game_launcher(script):
    """Return the key and value of the launcher"""
    launcher_value = None

    # exe64 can be provided to specify an executable for 64bit systems
    exe = "exe64" if "exe64" in script and system.LINUX_SYSTEM.is_64_bit else "exe"

    for launcher in (exe, "iso", "rom", "disk", "main_file"):
        if launcher not in script:
            continue
        launcher_value = script[launcher]

        if launcher == "exe64":
            launcher = "exe"  # If exe64 is used, rename it to exe

        break

    if not launcher_value:
        launcher = None
    return launcher, launcher_value


class ScriptInterpreter(CommandsMixin):
    """Convert raw installer script data into actions.

    Really fucked up class that tries to do way more than it should.
    """

    def __init__(self, installer, parent):
        self.error = None
        self.errors = []
        self.target_path = None
        self.parent = parent
        self.reversion_data = {}
        self.game_files = {}
        self.game_disc = None
        self.cancelled = False
        self.abort_current_task = None
        self.user_inputs = []
        self.steam_data = {}
        self.gog_data = {}
        self.script = installer.get("script")
        if not self.script:
            raise ScriptingError("This installer doesn't have a 'script' section")

        self.script_pretty = json.dumps(self.script, indent=4)

        self.install_start_time = None  # Time of the start of the install
        self.steam_poll = None  # Reference to the Steam poller that checks if games are downloaded
        self.current_command = None  # Current installer command when iterating through them
        self.current_file_id = None  # Current file when downloading / gathering files
        self.runners_to_install = []
        self.prev_states = []  # Previous states for the Steam installer

        self.version = installer["version"]
        self.slug = installer["slug"]
        self.year = installer.get("year")
        self.runner = installer["runner"]
        self.game_name = self.script.get("custom-name") or installer["name"]
        self.game_slug = installer["game_slug"]
        self.steamid = installer.get("steamid")
        self.gogid = installer.get("gogid")

        if not self.is_valid():
            raise ScriptingError(
                "Invalid script: \n{}".format("\n".join(self.errors)), self.script
            )

        self.files = self.script.get("files", [])
        self.requires = self.script.get("requires")
        self.extends = self.script.get("extends")

        self._check_binary_dependencies()
        self._check_dependency()
        if self.creates_game_folder:
            self.target_path = self.get_default_target()

        # If the game is in the library and uninstalled, the first installation
        # updates it
        existing_game = pga.get_game_by_field(self.game_slug, "slug")
        if existing_game and not existing_game["installed"]:
            self.game_id = existing_game["id"]
        else:
            self.game_id = None

    def get_default_target(self):
        """Return default installation dir"""
        config = LutrisConfig(runner_slug=self.runner)
        games_dir = config.system_config.get("game_path", os.path.expanduser("~"))
        return os.path.expanduser(os.path.join(games_dir, self.game_slug))

    @property
    def cache_path(self):
        """Return the directory used as a cache for the duration of the installation"""
        return os.path.join(settings.CACHE_DIR, "installer/%s" % self.game_slug)

    @property
    def creates_game_folder(self):
        """Determines if an install script should create a game folder for the game"""
        if self.requires:
            # Game is an extension of an existing game, folder exists
            return False
        if self.runner in ("steam", "winesteam"):
            # Steam games installs in their steamapps directory
            return False
        if self.files or self.script.get("game", {}).get("gog"):
            return True
        command_names = [list(c.keys())[0] for c in self.script.get("installer", [])]
        if "insert-disc" in command_names:
            return True
        return False

    # --------------------------
    # "Initial validation" stage
    # --------------------------

    def is_valid(self):
        """Return True if script is usable."""

        if not isinstance(self.script, dict):
            self.errors.append("Script must be a dictionary")
            # Return early since the method assumes a dict
            return False

        # Check that installers contains all required fields
        for field in ("runner", "game_name", "game_slug"):
            if not hasattr(self, field) or not getattr(self, field):
                self.errors.append("Missing field '%s'" % field)

        # Check that libretro installers have a core specified
        if self.runner == "libretro":
            if "game" not in self.script or "core" not in self.script["game"]:
                self.errors.append("Missing libretro core in game section")

        # Check that installers don't contain both 'requires' and 'extends'
        if self.script.get("requires") and self.script.get("extends"):
            self.errors.append("Scripts can't have both extends and requires")
        return not bool(self.errors)

    @staticmethod
    def _get_installed_dependency(dependency):
        """Return whether a dependency is installed"""
        game = pga.get_game_by_field(dependency, field="installer_slug")

        if not game:
            game = pga.get_game_by_field(dependency, "slug")
        if bool(game) and bool(game["directory"]):
            return game

    def _check_binary_dependencies(self):
        """Check if all required binaries are installed on the system.

        This reads a `require-binaries` entry in the script, parsed the same way as
        the `requires` entry.
        """
        binary_dependencies = unpack_dependencies(self.script.get("require-binaries"))
        for dependency in binary_dependencies:
            if isinstance(dependency, tuple):
                installed_binaries = {
                    dependency_option: bool(system.find_executable(dependency_option))
                    for dependency_option in dependency
                }
                if not any(installed_binaries.values()):
                    raise ScriptingError(
                        "This installer requires %s on your system"
                        % " or ".join(dependency)
                    )
            else:
                if not system.find_executable(dependency):
                    raise ScriptingError(
                        "This installer requires %s on your system" % dependency
                    )

    def _check_dependency(self):
        """When a game is a mod or an extension of another game, check that the base
        game is installed.
        If the game is available, install the game in the base game folder.
        The first game available listed in the dependencies is the one picked to base
        the installed on.
        """
        if self.extends:
            dependencies = [self.extends]
        else:
            dependencies = unpack_dependencies(self.requires)
        error_message = "You need to install {} before"
        for index, dependency in enumerate(dependencies):
            if isinstance(dependency, tuple):
                dependency_choices = [
                    self._get_installed_dependency(dep) for dep in dependency
                ]
                installed_games = [dep for dep in dependency_choices if dep]
                if not installed_games:
                    raise ScriptingError(error_message.format(" or ".join(dependency)))
                if index == 0:
                    self.target_path = installed_games[0]["directory"]
                    self.requires = installed_games[0]["installer_slug"]
            else:
                game = self._get_installed_dependency(dependency)
                if not game:
                    raise ScriptingError(error_message.format(dependency))
                if index == 0:
                    self.target_path = game["directory"]
                    self.requires = game["installer_slug"]

    # ---------------------
    # "Get the files" stage
    # ---------------------

    def swap_gog_game_files(self):
        if not self.gogid:
            raise ScriptingError("The installer has no GOG ID!")
        links = self.get_gog_download_links()
        installer_file_id = None
        if links:
            for index, file in enumerate(self.files):
                file_id = list(file.keys())[0]
                file_meta = file[file_id]
                if (
                        (
                            isinstance(file_meta, str)
                            and file_meta.startswith("N/A")
                        ) or (
                            isinstance(file_meta, dict)
                            and file_meta.get('url', '').startswith('N/A')
                        )
                ):
                    logger.debug("Removing file %s", file_id)
                    self.files.pop(index)
                    installer_file_id = file_id
                    break

        if not installer_file_id:
            raise ScriptingError("Could not match a GOG installer file in the files")

        for index, link in enumerate(links):

            filename = link.split("?")[0].split("/")[-1]

            if filename.lower().endswith((".exe", ".sh")):
                file_id = installer_file_id
            else:
                file_id = "gog_file_%s" % index

            logger.debug("Adding GOG file %s as %s", filename, file_id)

            self.files.append({
                file_id: {
                    "url": link,
                    "filename": filename,
                }
            })

    def prepare_game_files(self):
        """Gathers necessary files before iterating through them."""
        # If this is a GOG installer, download required files.
        if self.version.startswith("GOG"):
            self.swap_gog_game_files()
        self.iter_game_files()

    def iter_game_files(self):
        """Iterate through game files, downloading them or querying them from the user"""
        if self.files:
            # Create cache dir if needed
            if not os.path.exists(self.cache_path):
                os.mkdir(self.cache_path)

            if (
                    self.target_path
                    and not system.path_exists(self.target_path)
                    and self.creates_game_folder
            ):
                try:
                    os.makedirs(self.target_path)
                except PermissionError:
                    raise ScriptingError(
                        "Lutris does not have the necessary permissions to install to path:",
                        self.target_path,
                    )
                self.reversion_data["created_main_dir"] = True

        if len(self.game_files) < len(self.files):
            logger.info(
                "Downloading file %d of %d", len(self.game_files) + 1, len(self.files)
            )
            file_index = len(self.game_files)
            try:
                current_file = self.files[file_index]
            except KeyError:
                raise ScriptingError(
                    "Error getting file %d in %s" % file_index, self.files
                )
            self._download_file(current_file)
        else:
            self.current_command = 0
            self._prepare_commands()

    def _download_file(self, game_file):
        """Download a file referenced in the installer script.

        KILL IT WITH FIRE!!! This method is a mess.

        Game files can be either a string, containing the location of the
        file to fetch or a dict with the following keys:
        - url : location of file, if not present, filename will be used
                this should be the case for local files.
        - filename : force destination filename when url is present or path
                     of local file.
        """
        if not isinstance(game_file, dict):
            raise ScriptingError("Invalid file, check the installer script", game_file)
        # Setup file_id, file_uri and local filename
        file_id = list(game_file.keys())[0]
        file_meta = game_file[file_id]
        if isinstance(file_meta, dict):
            for field in ("url", "filename"):
                if field not in file_meta:
                    raise ScriptingError(
                        "missing field `%s` for file `%s`" % (field, file_id)
                    )
            file_uri = file_meta["url"]
            filename = file_meta["filename"]
            referer = file_meta.get("referer")
            checksum = file_meta.get("checksum")
        else:
            file_uri = file_meta
            filename = os.path.basename(file_uri)
            referer = None
            checksum = None

        if file_uri.startswith("/"):
            file_uri = "file://" + file_uri
        elif file_uri.startswith(("$WINESTEAM", "$STEAM")):
            # Download Steam data
            self._download_steam_data(file_uri, file_id)
            return

        if not filename:
            raise ScriptingError(
                "No filename provided, please provide 'url' and 'filename' parameters in the script"
            )

        # Check for file availability in PGA
        pga_uri = pga.check_for_file(self.game_slug, file_id)
        if pga_uri:
            file_uri = pga_uri

        # Setup destination path
        dest_file = os.path.join(self.cache_path, filename)

        logger.debug("Downloading [%s]: %s to %s", file_id, file_uri, dest_file)

        if file_uri.startswith("N/A"):
            # Ask the user where the file is located
            parts = file_uri.split(":", 1)
            if len(parts) == 2:
                message = parts[1]
            else:
                message = "Please select file '%s'" % file_id
            self.current_file_id = file_id
            self.parent.ask_user_for_file(message)
            return

        if os.path.exists(dest_file):
            os.remove(dest_file)

        # Change parent's status
        self.parent.set_status("")
        self.game_files[file_id] = dest_file

        if checksum:
            self.parent.start_download(
                file_uri,
                dest_file,
                lambda *args: self.check_hash(checksum, dest_file, file_uri),
                referer=referer
            )
        else:
            self.parent.start_download(file_uri, dest_file, referer=referer)

    def check_hash(self, checksum, dest_file, dest_file_uri):
        """Checks the checksum of `file` and compare it to `value`

        Args:
            checksum (str): The checksum to look for (type:hash)
            dest_file (str): The path to the destination file
            dest_file_uri (str): The uri for the destination file
        """

        try:
            hash_type, expected_hash = checksum.split(':', 1)
        except ValueError:
            raise ScriptingError("Invalid checksum, expected format (type:hash) ", dest_file_uri)

        if system.get_file_checksum(dest_file, hash_type) != expected_hash:
            raise ScriptingError(hash_type.capitalize() + " checksum mismatch ", dest_file_uri)

    def check_runner_install(self):
        """Check if the runner is installed before starting the installation
        Install the required runner(s) if necessary. This should handle runner
        dependencies (wine for winesteam) or runners used for installer tasks.
        """
        required_runners = []
        runner = self.get_runner_class(self.runner)
        if runner.depends_on is not None:
            required_runners.append(runner.depends_on())
        required_runners.append(runner())

        for command in self.script.get("installer", []):
            command_name, command_params = self._get_command_name_and_params(command)
            if command_name == "task":
                runner_name, _task_name = self._get_task_runner_and_name(
                    command_params["name"]
                )
                runner_names = [r.name for r in required_runners]
                if runner_name not in runner_names:
                    required_runners.append(self.get_runner_class(runner_name)())

        for runner in required_runners:
            params = {}
            if self.runner == "libretro":
                params["core"] = self.script["game"]["core"]
            if self.runner.startswith("wine"):
                params["min_version"] = wine.MIN_SAFE_VERSION
                version = self._get_runner_version()
                if version:
                    params["version"] = version
                    # Force the wine version to be installed
                    params["fallback"] = False
            if not runner.is_installed(**params):
                self.runners_to_install.append(runner)

        if self.runner.startswith("wine") and not get_system_wine_version():
            WineNotInstalledWarning(parent=self.parent)
        self.install_runners()

    def install_runners(self):
        """Install required runners for a game"""
        if self.runners_to_install:
            self.install_runner(self.runners_to_install.pop(0))
            return
        self.prepare_game_files()

    def install_runner(self, runner):
        """Install runner required by the install script"""
        logger.debug("Installing %s", runner.name)
        try:
            runner.install(
                version=self._get_runner_version(),
                downloader=self.parent.start_download,
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

    def file_selected(self, file_path):
        """Continue install after a file has been selected by the user"""
        file_id = self.current_file_id
        if not file_path or not os.path.exists(file_path):
            raise ScriptingError("Can't continue installation without file", file_id)
        self.game_files[file_id] = file_path
        self.prepare_game_files()

    # ---------------
    # "Commands" stage
    # ---------------

    def _prepare_commands(self):
        """Run the pre-installation steps and launch install."""
        if self.target_path and os.path.exists(self.target_path):
            os.chdir(self.target_path)

        if not os.path.exists(self.cache_path):
            os.mkdir(self.cache_path)

        # Add steam installation to commands if it's a Steam game
        if self.runner in ("steam", "winesteam"):
            try:
                self.steam_data["appid"] = self.script["game"]["appid"]
            except KeyError:
                raise ScriptingError("Missing appid for steam game")

            if "arch" in self.script["game"]:
                self.steam_data["arch"] = self.script["game"]["arch"]

            commands = self.script.get("installer", [])
            self.steam_data["platform"] = (
                "windows" if self.runner == "winesteam" else "linux"
            )
            commands.insert(0, "install_steam_game")
            self.script["installer"] = commands

        self._iter_commands()

    def _iter_commands(self, result=None, exception=None):
        if result == "STOP" or self.cancelled:
            return

        self.parent.set_status("Installing game data")
        self.parent.add_spinner()
        self.parent.continue_button.hide()

        commands = self.script.get("installer", [])
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

    # ----------------
    # "Finalize" stage
    # ----------------

    def _finish_install(self):
        game = self.script.get("game")
        launcher_value = None
        if game:
            _launcher, launcher_value = _get_game_launcher(game)
        path = None
        if launcher_value:
            path = self._substitute(launcher_value)
            if not os.path.isabs(path):
                path = os.path.join(self.target_path, path)
        self._write_config()
        if path and not os.path.isfile(path):
            self.parent.set_status(
                "The executable at path %s can't be found, please check the destination folder.\n"
                "Check the destination folder, "
                "some parts of the installation process may have not completed successfully." % path
            )
            logger.warning("No executable found at specified location %s", path)
        else:
            self.parent.set_status("Installation finished!")

        self.parent.on_install_finished()

    def _write_config(self):
        """Write the game configuration in the DB and config file.

        This needs to be unfucked
        """
        if self.extends:
            logger.info(
                "This is an extension to %s, not creating a new game entry",
                self.extends,
            )
            return
        configpath = make_game_config_id(self.slug)
        config_filename = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % configpath)

        if self.requires:
            # Load the base game config
            required_game = pga.get_game_by_field(self.requires, field="installer_slug")
            base_config = LutrisConfig(
                runner_slug=self.runner, game_config_id=required_game["configpath"]
            )
            config = base_config.game_level
        else:
            config = {"game": {}}

        self.game_id = pga.add_or_update(
            name=self.game_name,
            runner=self.runner,
            slug=self.game_slug,
            directory=self.target_path,
            installed=1,
            installer_slug=self.slug,
            parent_slug=self.requires,
            year=self.year,
            steamid=self.steamid,
            configpath=configpath,
            id=self.game_id,
        )

        game = Game(self.game_id)
        game.set_platform_from_runner()
        game.save()

        logger.debug("Saved game entry %s (%d)", self.game_slug, self.game_id)

        # Config update
        if "system" in self.script:
            config["system"] = self._substitute_config(self.script["system"])
        if self.runner in self.script and self.script[self.runner]:
            config[self.runner] = self._substitute_config(self.script[self.runner])

        # Game options such as exe or main_file can be added at the root of the
        # script as a shortcut, this integrates them into the game config
        # properly
        launcher, launcher_value = _get_game_launcher(self.script)
        if isinstance(launcher_value, list):
            game_files = []
            for game_file in launcher_value:
                if game_file in self.game_files:
                    game_files.append(self.game_files[game_file])
                else:
                    game_files.append(game_file)
            config["game"][launcher] = game_files
        elif launcher_value:
            if launcher_value in self.game_files:
                launcher_value = self.game_files[launcher_value]
            elif self.target_path and os.path.exists(
                    os.path.join(self.target_path, launcher_value)
            ):
                launcher_value = os.path.join(self.target_path, launcher_value)
            config["game"][launcher] = launcher_value

        if "game" in self.script:
            try:
                config["game"].update(self.script["game"])
            except ValueError:
                raise ScriptingError("Invalid 'game' section", self.script["game"])
            config["game"] = self._substitute_config(config["game"])

        yaml_config = yaml.safe_dump(config, default_flow_style=False)
        with open(config_filename, "w") as config_file:
            config_file.write(yaml_config)

    def _substitute_config(self, script_config):
        """Substitute values such as $GAMEDIR in a config dict."""
        config = {}
        for key in script_config:
            if not isinstance(key, str):
                raise ScriptingError("Game config key must be a string", key)
            value = script_config[key]
            if isinstance(value, list):
                config[key] = [self._substitute(i) for i in value]
            elif isinstance(value, dict):
                config[key] = {k: self._substitute(v) for (k, v) in value.items()}
            elif isinstance(value, bool):
                config[key] = value
            else:
                config[key] = self._substitute(value)
        return config

    # --------------------
    # "After the end" stage
    # --------------------

    def cleanup(self):
        """Clean up install dir after a successful install"""
        os.chdir(os.path.expanduser("~"))
        system.remove_folder(self.cache_path)

    # --------------
    # Revert install
    # --------------

    def revert(self):
        """Revert installation in case of an error"""
        logger.debug("Install cancelled")
        self.cancelled = True

        if self.abort_current_task:
            self.abort_current_task()

        if self.reversion_data.get("created_main_dir"):
            system.remove_folder(self.target_path)

    # -------------
    # Utility stuff
    # -------------

    def _substitute(self, template_string):
        """Replace path aliases with real paths."""
        replacements = {
            "GAMEDIR": self.target_path,
            "CACHE": self.cache_path,
            "HOME": os.path.expanduser("~"),
            "STEAM_DATA_DIR": steam.steam().steam_data_dir,
            "DISC": self.game_disc,
            "USER": os.getenv("USER"),
            "INPUT": self._get_last_user_input(),
            "VERSION": self.version,
        }
        # Add 'INPUT_<id>' replacements for user inputs with an id
        for input_data in self.user_inputs:
            alias = input_data["alias"]
            if alias:
                replacements[alias] = input_data["value"]

        replacements.update(self.game_files)
        return system.substitute(template_string, replacements)

    def _get_last_user_input(self):
        return self.user_inputs[-1]["value"] if self.user_inputs else ""

    def eject_wine_disc(self):
        """Use Wine to eject a CD, otherwise Wine can have problems detecting disc changes"""
        wine_path = get_wine_version_exe(self._get_runner_version())
        wine.eject_disc(wine_path, self.target_path)

    # -----------
    # Steam stuff
    # -----------

    def install_steam_game(self, runner_class=None, is_game_files=False):
        """Launch installation of a steam game.

        runner_class: class of the steam runner to use
        is_game_files: whether game data is added to game_files
        """

        # Check if Steam is installed, save the method's arguments so it can
        # be called again once Steam is installed.
        self.steam_data["callback_args"] = (runner_class, is_game_files)

        steam_runner = self._get_steam_runner(runner_class)
        self.steam_data["is_game_files"] = is_game_files
        appid = self.steam_data["appid"]

        if not steam_runner.get_game_path_from_appid(appid):
            logger.debug("Installing steam game %s", appid)
            steam_runner.config = LutrisConfig(runner_slug=steam_runner.name)
            if "arch" in self.steam_data:
                steam_runner.config.game_config["arch"] = self.steam_data["arch"]
            AsyncCall(steam_runner.install_game, self.on_steam_game_installed, appid, is_game_files)

            self.install_start_time = time.localtime()
            self.steam_poll = GLib.timeout_add(2000, self._monitor_steam_game_install)
            self.abort_current_task = lambda: steam_runner.remove_game_data(appid=appid)
            return "STOP"

        if is_game_files:
            self._append_steam_data_to_files(runner_class)
        else:
            self.target_path = self._get_steam_game_path()

    def on_steam_game_installed(self, _data, error):
        """Callback for Steam game installer, mostly for error handling since install progress
        is handled by _monitor_steam_game_install"""
        if error:
            raise ScriptingError(str(error))

    def _get_steam_runner(self, runner_class=None):
        if not runner_class:
            if self.runner == "steam":
                runner_class = steam.steam
            elif self.runner == "winesteam":
                runner_class = winesteam.winesteam
            elif self.steam_data["is_game_files"]:
                if self.steam_data["platform"] == "windows":
                    runner_class = winesteam.winesteam
                else:
                    runner_class = steam.steam
        return runner_class()

    def _monitor_steam_game_install(self):
        if self.cancelled:
            return False
        appid = self.steam_data["appid"]
        steam_runner = self._get_steam_runner()
        states = get_app_state_log(
            steam_runner.steam_data_dir, appid, self.install_start_time
        )
        if states != self.prev_states:
            logger.debug("Steam installation status:")
            logger.debug(states)
        self.prev_states = states

        if states and states[-1].startswith("Fully Installed"):
            logger.debug("Steam game has finished installing")
            self._on_steam_game_installed()
            return False
        return True

    def _on_steam_game_installed(self, *_args):
        """Fired whenever a Steam game has finished installing."""
        self.abort_current_task = None
        if self.steam_data["is_game_files"]:
            if self.steam_data["platform"] == "windows":
                runner_class = winesteam.winesteam
            else:
                runner_class = steam.steam
            self._append_steam_data_to_files(runner_class)
        else:
            self.target_path = self._get_steam_game_path()
            self._iter_commands()

    def _get_steam_game_path(self, runner_class=None):
        if not runner_class:
            steam_runner = self._get_steam_runner()
        else:
            steam_runner = runner_class()
        return steam_runner.get_game_path_from_appid(self.steam_data["appid"])

    def _append_steam_data_to_files(self, runner_class):
        data_path = self._get_steam_game_path(runner_class)
        if not data_path or not os.path.exists(data_path):
            raise ScriptingError("Unable to get Steam data for game")
        self.game_files[self.steam_data["file_id"]] = os.path.abspath(
            os.path.join(data_path, self.steam_data["steam_rel_path"])
        )
        self.prepare_game_files()

    def _download_steam_data(self, file_uri, file_id):
        """Download the game files from Steam to use them outside of Steam.

        file_uri: Colon separated game info containing:
                   - $STEAM or $WINESTEAM depending on the version of Steam
                     Since Steam for Linux can download games for any
                     platform, using $WINESTEAM has little value except in
                     some cases where the game needs to be started by Steam
                     in order to get a CD key (ie. Doom 3 or UT2004)
                   - The Steam appid
                   - The relative path of files to retrieve
        file_id: The lutris installer internal id for the game files
        """
        try:
            parts = file_uri.split(":", 2)
            steam_rel_path = parts[2].strip()
        except IndexError:
            raise ScriptingError("Malformed steam path: %s" % file_uri)
        if steam_rel_path == "/":
            steam_rel_path = "."
        self.steam_data = {
            "appid": parts[1],
            "steam_rel_path": steam_rel_path,
            "file_id": file_id,
        }

        logger.debug("Getting Steam data for appid %s", self.steam_data["appid"])

        self.parent.clean_widgets()
        self.parent.add_spinner()
        if parts[0] == "$WINESTEAM":
            self.parent.set_status("Getting Wine Steam game data")
            self.steam_data["platform"] = "windows"
            self.install_steam_game(winesteam.winesteam, is_game_files=True)
        else:
            # Getting data from Linux Steam
            self.parent.set_status("Getting Steam game data")
            self.steam_data["platform"] = "linux"
            self.install_steam_game(steam.steam, is_game_files=True)

    def get_gog_installers(self, gog_service):
        """Return available installers for a GOG game"""

        self.gog_data = gog_service.get_game_details(self.gogid)

        # Filter out Mac installers
        gog_installers = [
            installer
            for installer in self.gog_data["downloads"]["installers"]
            if installer["os"] != "mac"
        ]
        available_platforms = set([installer["os"] for installer in gog_installers])
        # If it's a Linux game, also filter out Windows games
        if "linux" in available_platforms:
            gog_installers = [
                installer
                for installer in gog_installers
                if installer["os"] != "windows"
            ]

        # Keep only the english installer until we have locale detection
        # and / or language selection implemented
        gog_installers = [
            installer
            for installer in gog_installers
            if installer["language"] == "en"
        ]
        return gog_installers

    def get_gog_download_links(self):
        """Return a list of downloadable links for a GOG game"""
        gog_service = GogService()
        if not gog_service.is_available():
            logger.info("You are not connected to GOG")
            connect_gog()
        gog_installers = self.get_gog_installers(gog_service)
        if len(gog_installers) > 1:
            raise ScriptingError("Don't know how to deal with multiple installers yet.")
        installer = gog_installers[0]
        download_links = []
        for game_file in installer.get('files', []):
            downlink = game_file.get("downlink")
            if not downlink:
                logger.error("No download information for %s", installer)
                continue
            download_info = gog_service.get_download_info(downlink)
            for field in ('checksum', 'downlink'):
                url = download_info[field]
                logger.info("Adding %s to download links", url)
                download_links.append(download_info[field])
        return download_links
