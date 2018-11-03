from lutris.runners.runner import Runner
from lutris.util import system


class osmose(Runner):
    human_name = "Osmose"
    description = "Sega Master System Emulator"
    platforms = ['Sega Master System']
    runner_executable = 'osmose/osmose'
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
            'default_path': 'game_path',
            'help': ("The game data, commonly called a ROM image.\n"
                     "Supported formats: SMS and GG files. ZIP compressed "
                     "ROMs are supported.")
        }
    ]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': False,
        }
    ]

    def play(self):
        """Run Sega Master System game"""
        arguments = [self.get_executable()]
        rom = self.game_config.get('main_file') or ''
        if not system.path_exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        if self.runner_config.get('fullscreen'):
            arguments.append('-fs')
            arguments.append('-bilinear')
        return {'command': arguments}
