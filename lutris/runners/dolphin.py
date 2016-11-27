import os
from lutris.runners.runner import Runner


class dolphin(Runner):
    description = "Gamecube and Wii emulator"
    human_name = "Dolphin"
    platform = "Gamecube, Wii"
    runner_executable = 'dolphin/dolphin-emu'
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ISO file"
        }
    ]
    runner_options = []

    system_options_override = [
        {
            'option': 'disable_runtime',
            'default': True,
        }
    ]

    def play(self):
        iso = self.game_config.get('main_file') or ''
        if not os.path.exists(iso):
            return {'error': 'FILE_NOT_FOUND', 'file': iso}
        return {'command': [self.get_executable(), '-e', iso]}
