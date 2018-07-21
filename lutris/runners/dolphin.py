import os
from lutris.runners.runner import Runner


class dolphin(Runner):
    description = "Gamecube and Wii emulator"
    human_name = "Dolphin"
    platforms = [
        'Nintendo Gamecube',
        'Nintendo Wii',
    ]
    runnable_alone = True
    runner_executable = 'dolphin/dolphin-emu'
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ISO file"
        },
        {
            'option': 'platform',
            'type': 'choice',
            'label': 'Platform',
            'choices': (
                ('Nintendo Gamecube', '0'),
                ('Nintendo Wii', '1')
            )
        }
    ]
    runner_options = []

    def get_platform(self):
        return self.platforms[int(self.game_config.get('platform') or 1)]

    def play(self):
        iso = self.game_config.get('main_file') or ''
        if not os.path.exists(iso):
            return {'error': 'FILE_NOT_FOUND', 'file': iso}
        return {'command': [self.get_executable(), '-e', iso]}
