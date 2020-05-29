# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class stella(Runner):
    description = "Atari 2600 emulator"
    human_name = "Stella"
    platforms = ["Atari 2600"]
    runnable_alone = True
    runner_executable = "stella/bin/stella"
    game_options = [
        {
            "option":
            "main_file",
            "type":
            "file",
            "label":
            "ROM file",
            "help": (
                "The game data, commonly called a ROM image.\n"
                "Supported formats: A26/BIN/ROM. GZIP and ZIP compressed "
                "ROMs are supported."
            ),
        }
    ]
    runner_options = []

    def play(self):
        cart = self.game_config.get("main_file") or ""
        if not system.path_exists(cart):
            return {"error": "FILE_NOT_FOUND", "file": cart}
        return {"command": [self.get_executable(), cart]}
