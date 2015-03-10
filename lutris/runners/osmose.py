# -*- coding: utf-8 -*-
"""Runner for Sega Master System"""
import os
from lutris import settings
from lutris.runners.runner import Runner


class osmose(Runner):
    """Sega Master System Emulator"""
    human_name = "Osmose"
    package = "osmose"
    executable = "osmose"
    platform = "Sega Master System"
    tarballs = {
        'i386': "osmose-0.9.96-i386.tar.gz",
        'x64': "osmose-0.9.96-x86_64.tar.gz",
    }
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'ROM file',
            'help': ("The game data, commonly called a ROM image.\n"
                     "Supported formats: SMS and GG files. ZIP compressed "
                     "ROMs are supported.")
        }
    ]
    runner_options = [
        {
            'option': 'fullscreen',
            'type': 'bool',
            'label': 'Fullscreen'
        },
        {
            'option': 'joy',
            'type': 'bool',
            'label': 'Use joystick'
        }
    ]

    def is_installed(self):
        if os.path.exists(self.get_executable()):
            return True
        else:
            return super(osmose, self).is_installed()

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'osmose/osmose')

    def play(self):
        """Run Sega Master System game"""
        arguments = [self.get_executable()]
        if self.runner_config.get('fullscreen'):
            arguments.append('-fs')
            arguments.append('-bilinear')
        if self.runner_config.get('joy'):
            arguments.append('-joy')
        rom = self.game_config.get('main_file') or ''
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        arguments.append(rom)
        return {'command': arguments}
