import os

from lutris import settings
from lutris.runners.runner import Runner


class citra(Runner):
    human_name = "Citra"
    platform = 'Nintendo 3DS'
    description = 'Nintendo 3DS emulator'
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label':  'ROM file',
        'help': ("The game data, commonly called a ROM image.")
    }]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'citra/citra-qt')

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        return {"command": arguments}
