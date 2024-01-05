"""libretro runner"""
import os
from gettext import gettext as _
from operator import itemgetter
from zipfile import ZipFile

import requests

from lutris import settings
from lutris.exceptions import GameConfigError, MissingGameExecutableError, UnspecifiedVersionError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.libretro import RetroConfig
from lutris.util.log import logger


def get_default_config_path(path=""):
    return os.path.join(settings.RUNNER_DIR, "retroarch", path)


def get_libretro_cores():
    cores = []
    runner_path = get_default_config_path()
    if not os.path.exists(runner_path):
        return []

    # Get core identifiers from info dir
    info_path = get_default_config_path("info")
    if not os.path.exists(info_path):
        req = requests.get(
            "http://buildbot.libretro.com/assets/frontend/info.zip",
            allow_redirects=True,
            timeout=5
        )
        if req.status_code == requests.codes.ok:  # pylint: disable=no-member
            with open(get_default_config_path('info.zip'), 'wb') as info_zip:
                info_zip.write(req.content)
            with ZipFile(get_default_config_path('info.zip'), 'r') as info_zip:
                info_zip.extractall(info_path)
        else:
            logger.error("Error retrieving libretro info archive from server: %s - %s", req.status_code, req.reason)
            return []
    # Parse info files to fetch display name and platform/system
    for info_file in os.listdir(info_path):
        if "_libretro.info" not in info_file:
            continue
        core_identifier = info_file.replace("_libretro.info", "")
        core_config = RetroConfig(os.path.join(info_path, info_file))
        if "categories" in core_config.keys() and "Emulator" in core_config["categories"]:
            core_label = core_config["display_name"] or ""
            core_system = core_config["systemname"] or ""
            cores.append((core_label, core_identifier, core_system))
    cores.sort(key=itemgetter(0))
    return cores


# List of supported libretro cores
# First element is the human readable name for the core with the platform's short name
# Second element is the core identifier
# Third element is the platform's long name
LIBRETRO_CORES = get_libretro_cores()


def get_core_choices():
    return [(core[0], core[1]) for core in LIBRETRO_CORES]


class libretro(Runner):
    human_name = _("Libretro")
    description = _("Multi-system emulator")
    runnable_alone = True
    runner_executable = "retroarch/retroarch"
    flatpak_id = "org.libretro.RetroArch"
    has_runner_versions = True

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file")
        },
        {
            "option": "core",
            "type": "choice",
            "label": _("Core"),
            "choices": get_core_choices(),
        },
    ]

    runner_options = [
        {
            "option": "config_file",
            "type": "file",
            "label": _("Config file"),
            "default": get_default_config_path("retroarch.cfg"),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "verbose",
            "type": "bool",
            "label": _("Verbose logging"),
            "default": False,
        },
    ]

    @property
    def directory(self):
        return os.path.join(settings.RUNNER_DIR, "retroarch")

    @property
    def platforms(self):
        return [core[2] for core in LIBRETRO_CORES]

    def get_platform(self):
        game_core = self.game_config.get("core")
        if not game_core:
            logger.warning("Game don't have a core set")
            return
        for core in LIBRETRO_CORES:
            if core[1] == game_core:
                return core[2]
        logger.warning("'%s' not found in Libretro cores", game_core)
        return ""

    def get_core_path(self, core):
        """Return the path of a core, prioritizing Retroarch cores"""
        lutris_cores_folder = os.path.join(self.directory, "cores")
        retroarch_core_folder = os.path.join(os.path.expanduser("~/.config/retroarch/cores"))
        core_filename = "{}_libretro.so".format(core)
        retroarch_core = os.path.join(retroarch_core_folder, core_filename)
        if system.path_exists(retroarch_core):
            return retroarch_core
        return os.path.join(lutris_cores_folder, core_filename)

    def get_version(self, use_default=True):
        return self.game_config["core"]

    def is_installed(self, flatpak_allowed: bool = True, core=None) -> bool:
        if not core and self.has_explicit_config and self.game_config.get("core"):
            core = self.game_config["core"]
        if not core or self.runner_config.get("runner_executable"):
            return super().is_installed(flatpak_allowed=flatpak_allowed)
        is_core_installed = system.path_exists(self.get_core_path(core))
        return super().is_installed(flatpak_allowed=flatpak_allowed) and is_core_installed

    def is_installed_for(self, interpreter):
        core = interpreter.installer.script["game"].get("core")
        return self.is_installed(core=core)

    def get_installer_runner_version(self, installer, use_runner_config: bool = True) -> str:
        version = installer.script["game"].get("core")
        if not version:
            raise UnspecifiedVersionError(_("The installer does not specify the libretro 'core' version."))
        return version

    async def install(self, install_ui_delegate, version=None):
        if not super().is_installed():
            if not await super().install(install_ui_delegate, version=None):
                return False
            if version:
                return super().install(install_ui_delegate, version)

            return True

        return await super().install(install_ui_delegate, version)

    def get_run_data(self):
        return {
            "command": self.get_command() + self.get_runner_parameters(),
            "env": self.get_env(),
        }

    def get_config_file(self):
        return self.runner_config.get("config_file") or get_default_config_path("retroarch.cfg")

    @staticmethod
    def get_system_directory(retro_config):
        """Return the system directory used for storing BIOS and firmwares."""
        system_directory = retro_config["system_directory"]
        if not system_directory or system_directory == "default":
            system_directory = get_default_config_path("system")
        return os.path.expanduser(system_directory)

    def prelaunch(self):
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        config_file = self.get_config_file()
        # TODO: review later
        # Create retroarch.cfg if it doesn't exist.
        if not system.path_exists(config_file):
            with open(config_file, "w", encoding='utf-8') as f:
                f.write("# Lutris RetroArch Configuration")
                f.close()

            # Build the default config settings.
            retro_config = RetroConfig(config_file)
            retro_config["libretro_directory"] = get_default_config_path("cores")
            retro_config["libretro_info_path"] = get_default_config_path("info")
            retro_config["content_database_path"] = get_default_config_path("database/rdb")
            retro_config["cheat_database_path"] = get_default_config_path("database/cht")
            retro_config["cursor_directory"] = get_default_config_path("database/cursors")
            retro_config["screenshot_directory"] = get_default_config_path("screenshots")
            retro_config["input_remapping_directory"] = get_default_config_path("remaps")
            retro_config["video_shader_dir"] = get_default_config_path("shaders")
            retro_config["core_assets_directory"] = get_default_config_path("downloads")
            retro_config["thumbnails_directory"] = get_default_config_path("thumbnails")
            retro_config["playlist_directory"] = get_default_config_path("playlists")
            retro_config["joypad_autoconfig_dir"] = get_default_config_path("autoconfig")
            retro_config["rgui_config_directory"] = get_default_config_path("config")
            retro_config["overlay_directory"] = get_default_config_path("overlay")
            retro_config["assets_directory"] = get_default_config_path("assets")
            retro_config.save()
        else:
            retro_config = RetroConfig(config_file)

        core = self.game_config.get("core")
        info_file = os.path.join(get_default_config_path("info"), "{}_libretro.info".format(core))
        if system.path_exists(info_file):
            retro_config = RetroConfig(info_file)
            try:
                firmware_count = int(retro_config["firmware_count"])
            except (ValueError, TypeError):
                firmware_count = 0
            system_path = self.get_system_directory(retro_config)
            notes = str(retro_config["notes"] or "")
            checksums = {}
            if notes.startswith("Suggested md5sums:"):
                parts = notes.split("|")
                for part in parts[1:]:
                    checksum, filename = part.split(" = ")
                    checksums[filename] = checksum
            for index in range(firmware_count):
                firmware_filename = retro_config["firmware%d_path" % index]
                firmware_path = os.path.join(system_path, firmware_filename)
                if system.path_exists(firmware_path):
                    if firmware_filename in checksums:
                        checksum = system.get_md5_hash(firmware_path)
                        if checksum == checksums[firmware_filename]:
                            checksum_status = "Checksum good"
                        else:
                            checksum_status = "Checksum failed"
                    else:
                        checksum_status = "No checksum info"
                    logger.info("Firmware '%s' found (%s)", firmware_filename, checksum_status)
                else:
                    logger.warning("Firmware '%s' not found!", firmware_filename)

                # Before closing issue #431
                # TODO check for firmware*_opt and display an error message if
                # firmware is missing
                # TODO Add dialog for copying the firmware in the correct
                # location

    def get_runner_parameters(self):
        parameters = []

        # Fullscreen
        fullscreen = self.runner_config.get("fullscreen")
        if fullscreen:
            parameters.append("--fullscreen")

        # Verbose
        verbose = self.runner_config.get("verbose")
        if verbose:
            parameters.append("--verbose")

        parameters.append("--config={}".format(self.get_config_file()))
        return parameters

    def play(self):
        command = self.get_command() + self.get_runner_parameters()

        # Core
        core = self.game_config.get("core")
        if not core:
            raise GameConfigError(_("No core has been selected for this game"))
        command.append("--libretro={}".format(self.get_core_path(core)))

        # Main file
        file = self.game_config.get("main_file")
        if not file:
            raise GameConfigError(_("No game file specified"))
        if not system.path_exists(file):
            raise MissingGameExecutableError(filename=file)
        command.append(file)
        return {"command": command}
