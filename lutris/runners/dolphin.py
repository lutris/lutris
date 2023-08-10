"""Dolphin runner"""
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system

PLATFORMS = [_("Nintendo GameCube"), _("Nintendo Wii")]


class dolphin(Runner):
    description = _("GameCube and Wii emulator")
    human_name = _("Dolphin")
    platforms = PLATFORMS
    require_libs = ["libOpenGL.so.0", ]
    runnable_alone = True
    runner_executable = "dolphin/dolphin-emu"
    flatpak_id = "org.DolphinEmu.dolphin-emu"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": _("ISO file"),
        },
        {
            "option": "platform",
            "type": "choice",
            "label": _("Platform"),
            "choices": ((_("Nintendo GameCube"), "0"), (_("Nintendo Wii"), "1")),
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
            "type": "directory_chooser",
            "advanced": True,
            "label": _("Custom Global User Directory"),
        },
    ]

    def get_platform(self):
        selected_platform = self.game_config.get("platform")
        if selected_platform:
            return self.platforms[int(selected_platform)]
        return ""

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
            return {"error": "FILE_NOT_FOUND", "file": iso}
        command.extend(["-e", iso])

        return {"command": command}
