import os

from lutris import settings
from lutris.runners.runner import Runner


class dgen(Runner):
    human_name = "DGen"
    description = "Sega Genesis emulator"
    platform = 'Sega Genesis'
    description = 'Sega Genesis (aka Sega Mega Drive) emulator'
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label':  'ROM file',
        'help': ("The game data, commonly called a ROM image.")
    }]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': True
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'dgen/bin/dgen')

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        if self.runner_config.get('fullscreen', True):
            arguments.append('-f')
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        return {"command": arguments}
