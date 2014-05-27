from lutris.runners.runner import Runner


class openmsx(Runner):
    """MSX computer emulator"""
    package = "openmsx"
    executable = "openmsx"
    platform = "MSX, MSX2, MSX2+, MSX turboR"
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
