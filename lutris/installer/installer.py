"""Lutris installer class"""

import json
from gettext import gettext as _

from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_or_update, get_game_by_field
from lutris.exceptions import AuthenticationError, UnavailableGameError
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.errors import ScriptingError
from lutris.installer.installer_file import InstallerFile
from lutris.runners import import_runner
from lutris.services import SERVICES
from lutris.util.game_finder import find_linux_game_executable, find_windows_game_executable
from lutris.util.gog import convert_gog_config_to_lutris, get_gog_config_from_path, get_gog_game_path
from lutris.util.log import logger
from lutris.util.moddb import ModDB, is_moddb_url
from lutris.util.system import fix_path_case


class LutrisInstaller:  # pylint: disable=too-many-instance-attributes
    """Represents a Lutris installer"""

    def __init__(self, installer, interpreter, service, appid):
        self.interpreter = interpreter
        self.installer = installer
        self.is_update = False

        try:
            self.version = installer["version"]
            self.slug = installer["slug"]
            self.year = installer.get("year")
            self.runner = installer["runner"]
            self.script = installer.get("script")
            self.game_name = installer["name"]
            self.game_slug = installer["game_slug"]
        except KeyError as ex:
            raise ScriptingError(_("The script was missing the '%s' key, which is required.") % ex.args[0]) from ex

        self.service = self.get_service(initial=service)
        self.service_appid = self.get_appid(installer, initial=appid)
        self.variables = self.script.get("variables", {})
        self.script_files = [
            InstallerFile(self.game_slug, file_id, file_meta)
            for file_desc in self.script.get("files", [])
            for file_id, file_meta in file_desc.items()
        ]
        self.files = []
        self.extra_file_paths = []
        self.requires = self.script.get("requires")
        self.extends = self.script.get("extends")
        self.game_id = self.get_game_id()
        self.is_gog = False
        self.discord_id = installer.get("discord_id")

    def get_service(self, initial=None):
        if initial:
            return initial
        if "steam" in self.runner and "steam" in SERVICES:
            return SERVICES["steam"]()
        version = self.version.lower()
        if "humble" in version and "humblebundle" in SERVICES:
            return SERVICES["humblebundle"]()
        if "gog" in version and "gog" in SERVICES:
            return SERVICES["gog"]()
        if "itch.io" in version and "itchio" in SERVICES:
            return SERVICES["itchio"]()

    def get_appid(self, installer, initial=None):
        if installer.get("is_dlc"):
            return installer.get("dlcid")
        if initial:
            return initial
        if not self.service:
            return
        service_id = None
        if self.service.id == "steam":
            service_id = installer.get("steamid") or installer.get("service_id")
        game_config = self.script.get("game", {})
        if self.service.id == "gog":
            service_id = game_config.get("gogid") or installer.get("gogid") or installer.get("service_id")
        if self.service.id == "humblebundle":
            service_id = game_config.get("humbleid") or installer.get("humblestoreid") or installer.get("service_id")
        if self.service.id == "itchio":
            service_id = game_config.get("itchid") or installer.get("itchid") or installer.get("service_id")
        if service_id:
            return service_id
        return

    @property
    def script_pretty(self):
        """Return a pretty print of the script"""
        return json.dumps(self.script, indent=4)

    def get_game_id(self):
        """Return the ID of the game in the local DB if one exists"""
        # If the game is in the library and uninstalled, the first installation
        # updates it
        existing_game = get_game_by_field(self.game_slug, "slug")
        if existing_game and (self.extends or not existing_game["installed"]):
            return existing_game["id"]

    @property
    def creates_game_folder(self):
        """Determines if an install script should create a game folder for the game"""
        if self.requires or self.extends:
            # Game is an extension of an existing game, folder exists
            return False
        if self.runner == "steam":
            # Steam games installs in their steamapps directory
            return False
        if not self.script.get("installer"):
            # No command can affect files
            return False
        if self.script_files or self.script.get("game", {}).get("gog") or self.script.get("game", {}).get("prefix"):
            return True
        command_names = [self.interpreter._get_command_name_and_params(c)[0] for c in self.script.get("installer", [])]
        if "insert_disc" in command_names:
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
        if self.runner == "steam":
            if not self.script.get("game", {}).get("appid"):
                errors.append("Missing appid for Steam game")

        # Check that installers don't contain both 'requires' and 'extends'
        if self.script.get("requires") and self.script.get("extends"):
            errors.append("Scripts can't have both extends and requires")
        return errors

    def prepare_game_files(self, extras, patch_version=None):
        """Gathers necessary files before iterating through them."""
        if not self.script_files:
            return

        installer_file_id = None
        installer_file_url = None
        if self.service:
            for file in self.script_files:
                if file.url.startswith("N/A"):
                    installer_file_id = file.id
                    installer_file_url = file.url
                    break
        files = [file.copy() for file in self.script_files if file.id != installer_file_id]
        extra_file_paths = []

        # Run variable substitution on the URLs from the script
        for file in files:
            file.set_url(self.interpreter._substitute(file.url))
            if is_moddb_url(file.url):
                file.set_url(ModDB().transform_url(file.url))

        if installer_file_id and self.service:
            logger.info("Getting files for %s", installer_file_id)
            try:
                if patch_version:
                    # If a patch version is given download the patch files instead of the installer
                    installer_files = self.service.get_patch_files(self, installer_file_id)
                else:
                    content_files, extra_files = self.service.get_installer_files(self, installer_file_id, extras)
                    extra_file_paths = [path for f in extra_files for path in f.get_dest_files_by_id().values()]
                    installer_files = content_files + extra_files
            except (AuthenticationError, UnavailableGameError) as ex:
                logger.exception("Game not available: %s", ex)
                installer_files = None

            if installer_files:
                for installer_file in installer_files:
                    files.append(installer_file)
            else:
                # Failed to get the service game, put back a user provided file
                logger.debug("Unable to get files from service. Setting %s to manual.", installer_file_id)
                files.insert(
                    0, InstallerFile(self.game_slug, installer_file_id, {"url": installer_file_url, "filename": ""})
                )

        # Commit changes only at the end; this is more robust in this method is runner
        # my two threads concurrently- the GIL can probably save us. It's not desirable
        # to do this, but this is the easiest workaround.
        self.files = files
        self.extra_file_paths = extra_file_paths

    def install_extras(self):
        # Copy extras to game folder; this updates the installer script, so it needs
        # be called just once, before launching the installers commands.
        if self.extra_file_paths and len(self.extra_file_paths) == len(self.files):
            # Reset the install script in case there are only extras.
            logger.warning("Installer with only extras and no game files")
            self.script["installer"] = []

        for extra_file in self.extra_file_paths:
            self.script["installer"].append({"copy": {"src": extra_file, "dst": "$GAMEDIR/extras"}})

    def _substitute_config(self, script_config):
        """Substitute values such as $GAMEDIR in a config dict."""
        config = {}
        for key in script_config:
            if not isinstance(key, str):
                raise ScriptingError(_("Game config key must be a string"), key)
            value = script_config[key]
            if str(value).lower() == "true":
                value = True
            if str(value).lower() == "false":
                value = False
            if key == "launch_configs":
                config[key] = [{k: self.interpreter._substitute(v) for (k, v) in _conf.items()} for _conf in value]
            elif isinstance(value, list):
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
            if not required_game:
                required_game = get_game_by_field(self.requires, field="slug")
            if not required_game:
                raise ValueError("No game matched '%s' on installer_slug or slug" % self.requires)
            base_config = LutrisConfig(runner_slug=self.runner, game_config_id=required_game["configpath"])
            config = base_config.game_level
        else:
            config = {"game": {}}

        # Config update
        if "system" in self.script:
            config["system"] = self._substitute_config(self.script["system"])
        if self.script.get(self.runner):
            installer_runner_config = self._substitute_config(self.script[self.runner])
            import_runner(self.runner)().adjust_installer_runner_config(installer_runner_config)
            config[self.runner] = installer_runner_config

        game_config = config["game"]

        entry_point_keys = ("iso", "rom", "main_file", "exe")

        if "game" in self.script:
            try:
                game_config.update(self.script["game"])
            except ValueError as err:
                raise ScriptingError(_("Invalid 'game' section"), faulty_data=self.script["game"]) from err

        # Obsolete install scripts may have the entry point key at root level;
        # we'll move them into the game-config if so, and if they are not already
        # there. Add a warning because I'm sure this compatibility ship will get lost,
        # and the scripts would be better updated.
        for entry_point_key in entry_point_keys:
            if entry_point_key in self.script and entry_point_key not in game_config:
                logger.warning("Moving entry point '%s' from script root level to the game config", entry_point_key)
                game_config[entry_point_key] = self.script[entry_point_key]

        game_config = self._substitute_config(game_config)
        if AUTO_ELF_EXE in game_config.get("exe", ""):
            game_config["exe"] = find_linux_game_executable(self.interpreter.target_path, make_executable=True)
        elif AUTO_WIN32_EXE in game_config.get("exe", ""):
            game_config["exe"] = find_windows_game_executable(self.interpreter.target_path)

        # Fix possible case differences
        for key in entry_point_keys:
            entry_point = game_config.get(key)
            if entry_point:
                game_config[key] = fix_path_case(entry_point)

        config["game"] = game_config
        config["name"] = self.game_name
        config["script"] = self.script
        config["variables"] = self.variables
        config["version"] = self.version
        config["requires"] = self.requires
        config["slug"] = self.slug
        config["game_slug"] = self.game_slug
        config["year"] = self.year
        if self.service:
            config["service"] = self.service.id
            config["service_id"] = self.service_appid
        return config

    def save(self):
        """Write the game configuration in the DB and config file"""
        if self.extends:
            logger.info(
                "This is an extension to %s, not creating a new game entry",
                self.extends,
            )
            return self.game_id

        if self.is_gog:
            gog_config = get_gog_config_from_path(self.interpreter.target_path)
            if gog_config:
                gog_game_path = get_gog_game_path(self.interpreter.target_path)
                lutris_config = convert_gog_config_to_lutris(gog_config, gog_game_path)
                self.script["game"].update(lutris_config)

        configpath = write_game_config(self.slug, self.get_game_config())
        self.game_id = add_or_update(
            name=self.game_name,
            runner=self.runner,
            slug=self.game_slug,
            platform=import_runner(self.runner)().get_platform(),
            directory=self.interpreter.target_path,
            installed=1,
            installer_slug=self.slug,
            parent_slug=self.requires,
            year=self.year,
            configpath=configpath,
            service=self.service.id if self.service else None,
            service_id=self.service_appid,
            id=self.game_id,
            discord_id=self.discord_id,
        )
        return self.game_id
