# -*- coding: utf-8 -*-
import os
from lutris.runners.runner import Runner


class mupen64plus(Runner):
    """Nintendo 64 emulator"""
    package = 'mupen64plus'
    executable = 'mupen64plus'
    platform = "Nintendo 64"
    game_options = [{
        'option': 'main_file',
        'type': 'file',
        'label': 'Rom File'
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
            'label': 'Hide gui',
            'default': True
        }
    ]

    def play(self):
        arguments = [self.executable]
        if self.runner_config.get('nogui'):
            arguments.append('--nogui')
        if self.runner_config.get('fullscreen'):
            arguments.append('--fullscreen')
        rom = self.settings['game'].get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append("\"%s\"" % rom)
        return {'command': arguments}
