import os
from lutris import settings
from lutris.runners.runner import Runner


class virtualjaguar(Runner):
    description = "Atari Jaguar emulator"
    human_name = "Virtual Jaguar"
    platform = "Atari Jaguar"
    runnable_alone = True

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

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'virtualjaguar/virtualjaguar')

    def play(self):
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        return {'command': [self.get_executable(), rom]}
