import os
from lutris.runners.runner import Runner


class pcsx2(Runner):
    human_name = "PCSX2"
    description = "Playstation 2 emulator"
    platform = "Sony Playstation 2"
    runner_executable = 'pcsx2/PCSX2'
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ISO file',
            'default_path': 'game_path'
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
        arguments = [self.get_executable()]

        if self.runner_config.get('fullscreen'):
            arguments.append('--fullscreen')

        iso = self.game_config.get('main_file') or ''
        if not os.path.exists(iso):
            return {'error': 'FILE_NOT_FOUND', 'file': iso}
        arguments.append(iso)
        return {'command': arguments}
