# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner


class mupen64plus(Runner):
    """Nintendo 64 emulator"""
    platform = "Nintendo 64"
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label': 'Rom file',
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
            'option': 'nogui',
            'type': 'bool',
            'label': 'Hide GUI',
            'default': True
        }
    ]
    tarballs = {
        'i386': 'mupen64plus-bundle-linux32-2.0.tar.gz',
        'x64': 'mupen64plus-bundle-linux64-2.0-ubuntu.tar.gz',
    }

    @property
    def working_dir(self):
        return os.path.join(settings.RUNNER_DIR, 'mupen64plus')

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'mupen64plus/mupen64plus')

    def play(self):
        arguments = [self.get_executable()]
        if self.runner_config.get('nogui'):
            arguments.append('--nogui')
        if self.runner_config.get('fullscreen'):
            arguments.append('--fullscreen')
        rom = self.settings['game'].get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append("\"%s\"" % rom)
        return {'command': arguments}
