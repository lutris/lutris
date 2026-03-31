"""Dolphin runner"""

from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system

PLATFORMS = [_("Nintendo GameCube"), _("Nintendo Wii")]


class dolphin(Runner):
    description = _("GameCube and Wii emulator")
    human_name = _("Dolphin")
    platform_dict = {"Nintendo GameCube": "0", "Nintendo Wii": "1"}
    require_libs = [
        "libOpenGL.so.0",
    ]
    runnable_alone = True
    runner_executable = "dolphin/Dolphin_Emulator-2512-anylinux-x86_64.AppImage"
    flatpak_id = "org.DolphinEmu.dolphin-emu"
    download_url = "https://github.com/pkgforge-dev/Dolphin-emu-AppImage/releases/download/2512%402026-01-26_1769467304/Dolphin_Emulator-2512-anylinux-x86_64.AppImage"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ISO file"),
        },
        {
            "option": "platform",
            "type": "choice",
            "label": _("Platform"),
            "choices": platform_dict,
            "default": next(iter(platform_dict.values())),
        },
    ]
    runner_options = [
        {
            "option": "batch",
            "type": "bool",
            "label": _("Batch"),
            "default": True,
            "advanced": True,
            "help": _("Exit Dolphin with emulator."),
        },
        {
            "option": "user_directory",
            "type": "directory",
            "warn_if_non_writable_parent": True,
            "advanced": True,
            "label": _("Custom Global User Directory"),
        },
    ]

    def play(self):
        command = self.get_command()

        # Batch isn't available in nogui
        if self.runner_config.get("batch"):
            command.append("--batch")

        # Custom Global User Directory
        if self.runner_config.get("user_directory"):
            command.append("-u")
            command.append(self.runner_config["user_directory"])

        # Retrieve the path to the file
        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            raise MissingGameExecutableError(filename=iso)
        command.extend(["-e", iso])

        return {"command": command}
