from lutris.runners.runner import Runner


class openmsx(Runner):
    """MSX computer emulator"""
    human_name = "openMSX"
    package = "openmsx"
    executable = "openmsx"
    platform = "MSX, MSX2, MSX2+, MSX turboR"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            'help': ("The game data, commonly called a ROM image.")
        }
    ]

    def play(self):
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.executable, "\"%s\"" % rom]}
