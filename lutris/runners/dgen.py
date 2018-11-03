from lutris.runners.runner import Runner
from lutris.util import system


class dgen(Runner):
    human_name = "DGen"
    description = "Sega Genesis emulator"
    platforms = ['Sega Genesis']
    runner_executable = 'dgen/bin/dgen'
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label': 'ROM file',
        'help': "The game data, commonly called a ROM image."
    }]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen',
            'default': True
        }
    ]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        if self.runner_config.get('fullscreen', True):
            arguments.append('-f')
        rom = self.game_config.get('main_file') or ''
        if not system.path_exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        return {"command": arguments}
