import os
from lutris.runners.runner import Runner


class melonds(Runner):
    human_name = "melonDS"
    description = "Nintendo DS Emulator"
    platforms = ['Nintendo DS']
    runner_executable = 'melonDS/melonDS'
    game_options = [
    	{
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
            'default_path': 'game_path'
        }
    ]

    def play(self):
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.get_executable(), rom]}
