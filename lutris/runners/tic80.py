from lutris.runners.runner import Runner
from lutris.util import system


class tic80(Runner):
    human_name = "TIC-80"
    description = "TIC-80 tiny computer"
    platforms = ["TIC-80"]
    runner_executable = "tic80/tic80"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {"option": "surf", "type": "bool", "label": "Start in Surf", "default": False},
        {
            "option": "skip",
            "type": "bool",
            "label": "Skip startup animation",
            "default": False,
        },
        {
            "option": "nosound",
            "type": "bool",
            "label": "Start in silent mode",
            "default": False,
        },
    ]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        if self.runner_config.get("surf"):
            arguments.append("-surf")
        if self.runner_config.get("skip"):
            arguments.append("-skip")
        if self.runner_config.get("nosound"):
            arguments.append("-nosound")
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}
        arguments.append(rom)
        return {"command": arguments}
