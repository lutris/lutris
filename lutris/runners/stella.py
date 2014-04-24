"""Runner for stella Atari 2600 emulator"""
from lutris.runners.runner import Runner


class stella(Runner):
    """Atari 2600 games emulator"""
    package = "stella"
    executable = "stella"
    platform = "Atari 2600"
    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": "Cartridge"
    }]
    runner_options = []

    def play(self):
        cart = self.settings["game"]["main_file"]
        return {'command': ['stella', "\"%s\"" % cart]}
