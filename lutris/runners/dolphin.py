from lutris.runners.runner import Runner
from lutris.util import system
import os


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
    runner_options = []

    def get_platform(self):
        selected_platform = self.game_config.get("platform")
        if selected_platform:
            return self.platforms[int(selected_platform)]
        return ""

    def play(self):
        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            return {"error": "FILE_NOT_FOUND", "file": iso}
        return {"command": [self.get_executable(), "-e", iso]}
