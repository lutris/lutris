from lutris.runners.runner import Runner
from lutris.util import system


class yuzu(Runner):
    human_name = "Yuzu"
    platforms = ["Nintendo Switch"]
    description = "Nintendo Switch emulator"
    runnable_alone = True
    runner_executable = "yuzu/yuzu"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "help": "The game data, commonly called a ROM image.",
        }
    ]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}
        arguments.append(rom)
        return {"command": arguments}
