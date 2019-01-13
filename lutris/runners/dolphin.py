"""Dolphin runner"""
from lutris.runners.runner import Runner
from lutris.util import system


class dolphin(Runner):
    description = "Gamecube and Wii emulator"
    human_name = "Dolphin"
    platforms = ["Nintendo Gamecube", "Nintendo Wii"]
    runnable_alone = True
    runner_executable = "dolphin/dolphin-emu"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ISO file",
        },
        {
            "option": "platform",
            "type": "choice",
            "label": "Platform",
            "choices": (("Nintendo Gamecube", "0"), ("Nintendo Wii", "1")),
        },
    ]
    runner_options = [
        {
            "option": "nogui",
            "type": "bool",
            "label": "No GUI",
            "default": False,
            "help": "Disable the graphical user interface.",
        },
        {
            "option": "batch",
            "type": "bool",
            "label": "Batch",
            "default": False,
            "help": "Exit Dolphin with emulator.",
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
