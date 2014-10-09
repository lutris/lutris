import os

from lutris import settings
from lutris.runners.runner import Runner


class gens(Runner):
    """Runner for Sega Genesis games"""
    executable = 'gens'
    platform = 'Sega Genesis'
    description = 'Sega Genesis emulator.'
    tarballs = {
        'i386': 'gens-2.16.7-i386.tar.gz',
        'x64': 'gens-2.16.7-i386.tar.gz',
    }
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
        },
        {
            'option': 'quickexit',
            'type': 'bool',
            'label': 'Exit emulator with Esc',
            'default': True
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'gens/gens')

    def play(self):
        """ Run the game """
        arguments = [self.get_executable()]
        if self.runner_config.get('fullscreen', True):
            arguments.append('--fs')
        else:
            arguments.append('--window')
        if self.runner_config.get('quickexit', True):
            arguments.append('--quickexit')
        rom = self.settings['game']['main_file']
        plugins_dir = os.path.join(os.path.expanduser('~'), '.gens/plugins')
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append("--game \"%s\"" % rom)
        return {"command": arguments}
