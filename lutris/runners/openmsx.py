from lutris.runners.runner import Runner


class openmsx(Runner):
    """Runner for MSX games"""
    package = "openmsx"
    executable = "openmsx"
    platform = "MSX"
    description = "MSX Emulator"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM File"
        }
    ]

    def play(self):
        rom = self.settings["game"]["main_file"]
        return {'command': [self.executable, "\"%s\"" % rom]}
