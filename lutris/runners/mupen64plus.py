# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system


class mupen64plus(Runner):
    human_name = "Mupen64Plus"
    description = "Nintendo 64 emulator"
    platforms = ['Nintendo 64']
    runner_executable = 'mupen64plus/mupen64plus'
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
        },
        {
            'option': 'hideosd',
            'type': 'bool',
            'label': 'Hide OSD',
            'default': True
        }
    ]

    @property
    def working_dir(self):
        return os.path.join(settings.RUNNER_DIR, 'mupen64plus')

    def play(self):
        arguments = [self.get_executable()]
        if self.runner_config.get('hideosd'):
            arguments.append('--noosd')
        else:
            arguments.append('--osd')
        if self.runner_config.get('fullscreen'):
            arguments.append('--fullscreen')
        else:
            arguments.append('--windowed')
        rom = self.game_config.get('main_file') or ''
        if not system.path_exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        return {'command': arguments}
