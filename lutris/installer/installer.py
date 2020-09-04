"""Lutris installer class"""
import json
import os

import yaml

from lutris import pga, settings
from lutris.config import LutrisConfig, make_game_config_id
from lutris.game import Game
from lutris.installer.errors import ScriptingError
from lutris.installer.installer_file import InstallerFile
from lutris.services import UnavailableGame
from lutris.services.gog import MultipleInstallerError, get_gog_download_links
from lutris.services.humblebundle import get_humble_download_link
from lutris.util import system
from lutris.util.http import HTTPError
from lutris.util.log import logger


class LutrisInstaller:  # pylint: disable=too-many-instance-attributes
    """Represents a Lutris installer"""
    def __init__(self, installer, interpreter):
        self.interpreter = interpreter
        self.version = installer["version"]
        self.slug = installer["slug"]
        self.year = installer.get("year")
        self.runner = installer["runner"]
        self.script = installer.get("script")
        self.game_name = self.script.get("custom-name") or installer["name"]
        self.game_slug = installer["game_slug"]
        self.steamid = installer.get("steamid")
        game_config = self.script.get("game", {})
        self.gogid = game_config.get("gogid") or installer.get("gogid")
        self.humbleid = game_config.get("humbleid") or installer.get("humblestoreid")

        self.files = [
            InstallerFile(self.game_slug, file_id, file_meta)
            for file_desc in self.script.get("files", [])
            for file_id, file_meta in file_desc.items()
        ]
        self.requires = self.script.get("requires")
        self.extends = self.script.get("extends")
        self.game_id = self.get_game_id()

    @property
    def script_pretty(self):
        """Return a pretty print of the script"""
        return json.dumps(self.script, indent=4)

    def get_game_id(self):
        """Return the ID of the game in the local DB if one exists"""
        # If the game is in the library and uninstalled, the first installation
        # updates it
        existing_game = pga.get_game_by_field(self.game_slug, "slug")
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

    def swap_steam_install(self):
        """Add steam installation to commands if it's a Steam game"""
        # XXX Steam is no longer an install command, it's a file
        # if self.runner in ("steam", "winesteam"):
        #     self.steam_data["appid"] = self.script["game"]["appid"]
        #     if "arch" in self.script["game"]:
        #         self.steam_data["arch"] = self.script["game"]["arch"]

        #     commands = self.script.get("installer", [])
        #     self.steam_data["platform"] = (
        #         "windows" if self.runner == "winesteam" else "linux"
        #     )
        #     commands.insert(0, "install_steam_game")
        #     self.script["installer"] = commands

    def swap_gog_game_files(self):
        """Replace user provided file with downloads from GOG"""
        logger.info("Swap GOG game files")
        if not self.gogid:
            raise UnavailableGame("The installer has no GOG ID!")
        try:
            links = get_gog_download_links(self.gogid, self.runner)
        except HTTPError:
            raise UnavailableGame("Couldn't load the download links for this game")
        except MultipleInstallerError:
            raise UnavailableGame("Don't know how to deal with multiple installers yet.")
        if not links:
            raise UnavailableGame("Could not fing GOG game")

        installer_file_id = self.pop_user_provided_file()
        if not installer_file_id:
            raise UnavailableGame("Installer has no user provided file")

        file_id_provided = False  # Only assign installer_file_id once
        for index, link in enumerate(links):
            if isinstance(link, dict):
                url = link["url"]
            else:
                url = link
            filename = url.split("?")[0].split("/")[-1]
            if filename.lower().endswith((".exe", ".sh")) and not file_id_provided:
                file_id = installer_file_id
                file_id_provided = True
            else:
                file_id = "gog_file_%s" % index
            self.files.append(
                InstallerFile(self.game_slug, file_id, {
                    "url": url,
                    "filename": filename,
                })
            )

    def pop_user_provided_file(self):
        """Return and remove the first user provided file, which is used for game stores
        """
        installer_file_id = None
        for index, file in enumerate(self.files):
            if file.url.startswith("N/A"):
                logger.debug("File %s detected as user provided, removing from files", file.id)
                self.files.pop(index)
                installer_file_id = file.id
                break
        return installer_file_id

    def prepare_game_files(self):
        """Gathers necessary files before iterating through them."""
        # If this is a GOG installer, download required files.
        version = self.version.lower()
        if version.startswith("gog"):
            logger.debug("GOG game detected")
            try:
                self.swap_gog_game_files()
            except UnavailableGame as ex:
                logger.error("Unable to get the game from GOG: %s", ex)
        if version.startswith("humble"):
            try:
                self.swap_humble_game_files()
            except UnavailableGame as ex:
                logger.error("Unable to get the game from GOG: %s", ex)
        if self.runner in ("steam", "winesteam"):
            steam_uri = "$WINESTEAM:%s:." if self.runner == "winesteam" else "$STEAM:%s:."
            appid = str(self.script["game"]["appid"])
            self.files.append(
                InstallerFile(self.game_slug, "steam_game", {
                    "url": steam_uri % appid,
                    "filename": appid
                })
            )

    def swap_humble_game_files(self):
        """Replace the user provided file with download links from Humble Bundle"""
        if not self.humbleid:
            raise UnavailableGame(
                "This installer has no Humble Bundle ID ('humbleid' in the game section)"
            )
        installer_file_id = self.pop_user_provided_file()
        if not installer_file_id:
            raise UnavailableGame("Installer has no user provided file")
        try:
            link = get_humble_download_link(self.humbleid, self.runner)
        except Exception as ex:
            logger.exception("Failed to get Humble Bundle game: %s", ex)
            raise UnavailableGame
        if not link:
            raise UnavailableGame("No game found on Humble Bundle")
        filename = link.split("?")[0].split("/")[-1]
        self.files.append(
            InstallerFile(self.game_slug, installer_file_id, {
                "url": link,
                "filename": filename
            })
        )

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

    def write_config(self):
        """Write the game configuration in the DB and config file"""
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
            directory=self.interpreter.target_path,
            installed=1,
            installer_slug=self.slug,
            parent_slug=self.requires,
            year=self.year,
            steamid=self.steamid,
            configpath=configpath,
            id=self.game_id,
        )

        game = Game(self.game_id)
        game.save()

        logger.debug("Saved game entry %s (%d)", self.game_slug, self.game_id)

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

        yaml_config = yaml.safe_dump(config, default_flow_style=False)
        with open(config_filename, "w") as config_file:
            config_file.write(yaml_config)

    def get_game_launcher_config(self, game_files):
        """Game options such as exe or main_file can be added at the root of the
        script as a shortcut, this integrates them into the game config properly
        """
        launcher, launcher_value = self.get_game_launcher()
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

    def get_game_launcher(self):
        """Return the key and value of the launcher"""
        launcher_value = None
        # exe64 can be provided to specify an executable for 64bit systems
        exe = "exe64" if "exe64" in self.script and system.LINUX_SYSTEM.is_64_bit else "exe"
        for launcher in (exe, "iso", "rom", "disk", "main_file"):
            if launcher not in self.script:
                continue
            launcher_value = self.script[launcher]
            if launcher == "exe64":
                launcher = "exe"  # If exe64 is used, rename it to exe
            break
        if not launcher_value:
            launcher = None
        return launcher, launcher_value
