import json
import os

# Standard Library
from gettext import gettext as _

from lutris.config import LutrisConfig
from lutris.exceptions import MissingGameExecutableError

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.firmware import get_firmware, scan_firmware_directory


class pcsx2(Runner):
    human_name = _("PCSX2")
    description = _("PlayStation 2 emulator")
    platforms = [_("Sony PlayStation 2")]
    runnable_alone = True
    runner_executable = "pcsx2/PCSX2"
    flatpak_id = "net.pcsx2.PCSX2"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ISO file"),
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": False,
        },
        {"option": "full_boot", "type": "bool", "label": _("Fullboot"), "default": False},
        {"option": "nogui", "type": "bool", "label": _("No GUI"), "default": False},
    ]

    # PCSX2 currently uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def prelaunch(self):
        RUNNER_FIRMWARE_DIR = os.path.expanduser("~/.config/PCSX2/bios")

        firmware_list_path = os.path.join(os.path.dirname(__file__), "static/pcsx2/firmwares.json")
        with open(firmware_list_path, "r") as firmwares_data:
            firmwares = json.load(firmwares_data)

            lutris_config = LutrisConfig()
            firmware_directory = lutris_config.raw_system_config["bios_path"]
            scan_firmware_directory(firmware_directory)

            for firmware in firmwares:
                get_firmware(firmware["filename"], firmware["checksum"], RUNNER_FIRMWARE_DIR)

    def play(self):
        arguments = self.get_command()

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        if self.runner_config.get("full_boot"):
            arguments.append("-slowboot")
        if self.runner_config.get("nogui"):
            arguments.append("-nogui")

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            raise MissingGameExecutableError(filename=iso)
        arguments.append(iso)
        return {"command": arguments}
