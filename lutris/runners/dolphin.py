"""Dolphin runner"""
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class dolphin(Runner):
    description = _("Gamecube and Wii emulator")
    human_name = _("Dolphin")
    platforms = [_("Nintendo Gamecube"), _("Nintendo Wii")]
    runnable_alone = True
    runner_executable = "dolphin/dolphin-emu"
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
            "choices": ((_("Nintendo Gamecube"), "0"), (_("Nintendo Wii"), "1")),
        },
    ]
    runner_options = [
        {
            "option": "nogui",
            "type": "bool",
            "label": _("No GUI"),
            "default": False,
            "help": _("Disable the graphical user interface."),
        },
        {
            "option": "batch",
            "type": "bool",
            "label": _("Batch"),
            "default": False,
            "help": _("Exit Dolphin with emulator."),
        },
    ]

    def get_platform(self):
        selected_platform = self.game_config.get("platform")
        if selected_platform:
            return self.platforms[int(selected_platform)]
        return ""

    def play(self):
        # Find the executable
        executable = self.get_executable()
        if self.runner_config.get("nogui"):
            executable += "-nogui"
        command = [executable]

        # Batch isn't available in nogui
        if self.runner_config.get("batch") and not self.runner_config.get("nogui"):
            command.append("--batch")

        # Retrieve the path to the file
        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            return {"error": "FILE_NOT_FOUND", "file": iso}
        command.extend(["-e", iso])

        return {"command": command}
