from lutris.runners.runner import Runner
from lutris.util import system


class openmsx(Runner):
    human_name = "openMSX"
    description = "MSX computer emulator"
    platforms = ["MSX, MSX2, MSX2+, MSX turboR"]
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            'help': "The game data, commonly called a ROM image."
        }
    ]

    def play(self):
        rom = self.game_config.get('main_file') or ''
        if not system.path_exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.get_executable(), rom]}
