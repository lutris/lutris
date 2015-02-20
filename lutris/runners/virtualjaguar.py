import os
from lutris import settings
from lutris.runners.runner import Runner


class virtualjaguar(Runner):
    """ Run Atari Jaguar games """
    human_name = "Virtual Jaguar"
    executable = "virtualjaguar"
    platform = "Atari Jaguar"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ROM file",
            'help': ("The game data, commonly called a ROM image.\n"
                     "Supported formats: J64 and JAG.")
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": "1"
        }
    ]

    tarballs = {
        'i386': None,
        'x64': 'virtualjaguar-2.1.1-x64.tar.gz'
    }

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'virtualjaguar/virtualjaguar')

    def play(self):
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.get_executable(), rom]}
