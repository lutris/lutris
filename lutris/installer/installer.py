"""Lutris installer class"""
import json
import os

import yaml

from lutris import settings
from lutris.config import LutrisConfig, make_game_config_id
from lutris.database.games import add_or_update, get_game_by_field
from lutris.game import Game
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.errors import ScriptingError
from lutris.installer.installer_file import InstallerFile
from lutris.installer.legacy import get_game_launcher
from lutris.runners import import_runner
from lutris.services import get_services
from lutris.util.game_finder import find_linux_game_executable, find_windows_game_executable
from lutris.util.log import logger


class LutrisInstaller:  # pylint: disable=too-many-instance-attributes
    """Represents a Lutris installer"""

    def __init__(self, installer, interpreter, service, appid):
        self.interpreter = interpreter
        self.installer = installer
        self.version = installer["version"]
        self.slug = installer["slug"]
        self.year = installer.get("year")
        self.runner = installer["runner"]
        self.script = installer.get("script")
        self.game_name = self.script.get("custom-name") or installer["name"]
        self.game_slug = installer["game_slug"]
        self.service = self.get_service(initial=service)
        self.service_appid = self.get_appid(installer, initial=appid)
        self.steamid = installer.get("steamid")
        self.files = [
            InstallerFile(self.game_slug, file_id, file_meta)
            for file_desc in self.script.get("files", [])
            for file_id, file_meta in file_desc.items()
        ]
        self.requires = self.script.get("requires")
        self.extends = self.script.get("extends")
        self.game_id = self.get_game_id()

    def get_service(self, initial=None):
        if initial:
            return initial
        if "steam" in self.runner:
            return get_services()["steam"]()
        version = self.version.lower()
        if "humble" in version:
            return get_services()["humblebundle"]()
        if "gog" in version:
            return get_services()["gog"]()

    def get_appid(self, installer, initial=None):
        if initial:
            return initial
        if not self.service:
            return
        if self.service.id == "steam":
            return installer.get("steamid")
        game_config = self.script.get("game", {})
        if self.service.id == "gog":
            return game_config.get("gogid") or installer.get("gogid")
        if self.service.id == "humblebundle":
            return game_config.get("humbleid") or installer.get("humblestoreid")

    @property
    def script_pretty(self):
        """Return a pretty print of the script"""
        return json.dumps(self.script, indent=4)

    def get_game_id(self):
        """Return the ID of the game in the local DB if one exists"""
        # If the game is in the library and uninstalled, the first installation
        # updates it
        existing_game = get_game_by_field(self.game_slug, "slug")
        if existing_game and not existing_game["installed"]:
            return existing_game["id"]

    @property
    def creates_game_folder(self):
        """Determines if an install script should create a game folder for the game"""
        if self.requires:
            # Game is an extension of an existing game, folder exists
            return False
        if self.runner in ("steam", "winesteam"):
            # Steam games installs in their steamapps directory
            return False
        if (
                self.files
                or self.script.get("game", {}).get("gog")
                or self.script.get("game", {}).get("prefix")
        ):
            return True
        command_names = [list(c.keys())[0] for c in self.script.get("installer", [])]
        if "insert-disc" in command_names:
            return True
        return False

    def get_errors(self):
        """Return potential errors in the script"""
        errors = []
        if not isinstance(self.script, dict):
            errors.append("Script must be a dictionary")
            # Return early since the method assumes a dict
            return errors

        # Check that installers contains all required fields
        for field in ("runner", "game_name", "game_slug"):
            if not hasattr(self, field) or not getattr(self, field):
                errors.append("Missing field '%s'" % field)

        # Check that libretro installers have a core specified
        if self.runner == "libretro":
            if "game" not in self.script or "core" not in self.script["game"]:
                errors.append("Missing libretro core in game section")

        # Check that Steam games have an AppID
        if self.runner in ("steam", "winesteam"):
            if not self.script.get("game", {}).get("appid"):
                errors.append("Missing appid for Steam game")

        # Check that installers don't contain both 'requires' and 'extends'
        if self.script.get("requires") and self.script.get("extends"):
            errors.append("Scripts can't have both extends and requires")
        return errors

    def pop_user_provided_file(self):
        """Return and remove the first user provided file, which is used for game stores"""
        for index, file in enumerate(self.files):
            if file.url.startswith("N/A"):
                self.files.pop(index)
                return file.id

    def prepare_game_files(self):
        """Gathers necessary files before iterating through them."""
        if not self.files:
            return
        if self.service:
            installer_file_id = self.pop_user_provided_file()
            if not installer_file_id:
                logger.warning("Could not find a file for this service")
                return
            logger.info("Should install %s", self.interpreter.extras)
            if self.service.has_extras:
                self.service.selected_extras = self.interpreter.extras
            installer_files = self.service.get_installer_files(self, installer_file_id)
            for installer_file in installer_files:
                self.files.append(installer_file)
            if not installer_files:
                # Failed to get the service game, put back a user provided file
                self.files.insert(0, "N/A: Provider installer file")

    def _substitute_config(self, script_config):
        """Substitute values such as $GAMEDIR in a config dict."""
        config = {}
        for key in script_config:
            if not isinstance(key, str):
                raise ScriptingError("Game config key must be a string", key)
            value = script_config[key]
            if str(value).lower() == 'true':
                value = True
            if str(value).lower() == 'false':
                value = False
            if isinstance(value, list):
                config[key] = [self.interpreter._substitute(i) for i in value]
            elif isinstance(value, dict):
                config[key] = {k: self.interpreter._substitute(v) for (k, v) in value.items()}
            elif isinstance(value, bool):
                config[key] = value
            else:
                config[key] = self.interpreter._substitute(value)
        return config

    def get_game_config(self):
        """Return the game configuration"""
        if self.requires:
            # Load the base game config
            required_game = get_game_by_field(self.requires, field="installer_slug")
            base_config = LutrisConfig(
                runner_slug=self.runner, game_config_id=required_game["configpath"]
            )
            config = base_config.game_level
        else:
            config = {"game": {}}

        # Config update
        if "system" in self.script:
            config["system"] = self._substitute_config(self.script["system"])
        if self.runner in self.script and self.script[self.runner]:
            config[self.runner] = self._substitute_config(self.script[self.runner])
        launcher, launcher_config = self.get_game_launcher_config(self.interpreter.game_files)
        if launcher:
            config["game"][launcher] = launcher_config

        if "game" in self.script:
            try:
                config["game"].update(self.script["game"])
            except ValueError:
                raise ScriptingError("Invalid 'game' section", self.script["game"])
            config["game"] = self._substitute_config(config["game"])
            if AUTO_ELF_EXE in config["game"].get("exe", ""):
                config["game"]["exe"] = find_linux_game_executable(self.interpreter.target_path,
                                                                   make_executable=True)
            elif AUTO_WIN32_EXE in config["game"].get("exe", ""):
                config["game"]["exe"] = find_windows_game_executable(self.interpreter.target_path)

        return config

    def write_game_config(self):
        configpath = make_game_config_id(self.slug)
        config_filename = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % configpath)
        config = self.get_game_config()
        yaml_config = yaml.safe_dump(config, default_flow_style=False)
        with open(config_filename, "w") as config_file:
            logger.debug("Writing game config to %s", config_filename)
            config_file.write(yaml_config)
        return configpath

    def save(self):
        """Write the game configuration in the DB and config file"""
        if self.extends:
            logger.info(
                "This is an extension to %s, not creating a new game entry",
                self.extends,
            )
            return
        configpath = self.write_game_config()
        runner_inst = import_runner(self.runner)()
        if self.service:
            service_id = self.service.id
        else:
            service_id = None
        self.game_id = add_or_update(
            name=self.game_name,
            runner=self.runner,
            slug=self.game_slug,
            platform=runner_inst.get_platform(),
            directory=self.interpreter.target_path,
            installed=1,
            installer_slug=self.slug,
            parent_slug=self.requires,
            year=self.year,
            steamid=self.steamid,
            configpath=configpath,
            service=service_id,
            service_id=self.service_appid,
            id=self.game_id,
        )
        # This is a bit redundant but used to trigger the game-updated signal
        game = Game(self.game_id)
        game.save()

    def get_game_launcher_config(self, game_files):
        """Game options such as exe or main_file can be added at the root of the
        script as a shortcut, this integrates them into the game config properly
        This should be deprecated. Game launchers should go in the game section.
        """
        launcher, launcher_value = get_game_launcher(self.script)
        if isinstance(launcher_value, list):
            launcher_values = []
            for game_file in launcher_value:
                if game_file in game_files:
                    launcher_values.append(game_files[game_file])
                else:
                    launcher_values.append(game_file)
            return launcher, launcher_values
        if launcher_value:
            if launcher_value in game_files:
                launcher_value = game_files[launcher_value]
            elif self.interpreter.target_path and os.path.exists(
                    os.path.join(self.interpreter.target_path, launcher_value)
            ):
                launcher_value = os.path.join(self.interpreter.target_path, launcher_value)
        return launcher, launcher_value
