import os
from lutris import settings
from lutris.runners.runner import Runner


class dolphin(Runner):
    description = "Gamecube and Wii emulator"
    human_name = "Dolphin"
    platform = "Gamecube, Wii"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": "ISO file"
        }
    ]
    runner_options = []

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'dolphin/dolphin-emu')

    def play(self):
        iso = self.game_config.get('main_file') or ''
        if not os.path.exists(iso):
            return {'error': 'FILE_NOT_FOUND', 'file': iso}
        return {'command': [self.get_executable(), '-e', iso]}
