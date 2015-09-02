# -*- coding: utf-8 -*-
# It is pitch black. You are likely to be eaten by a grue.

import os
from lutris import settings
from lutris.runners.runner import Runner


class frotz(Runner):
    """Z-code emulator for text adventure games such as Zork"""
    human_name = "Frotz"
    package = "frotz"
    executable = "frotz"
    platform = "Z-Code"

    tarballs = {
        'x64': 'frotz-2.44-x86_64.tar.gz',
    }

    game_options = [
        {
            "option": "story",
            "type": "file",
            "label": "Story file",
            'help': ('The Z-Machine game file.\n'
                     'Usally ends in ".z*", with "*" being a number from 1 '
                     'to 6 representing the version of the Z-Machine that '
                     'the game was written for.')
        }
    ]
    system_options_override = [
        {
            'option': 'terminal',
            'default': True,
        }
    ]

    def __init__(self, config=None):
        super(frotz, self).__init__(config)

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'frotz/frotz')

    def play(self):
        story = self.game_config.get('story') or ''
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED'}
        if not os.path.exists(story):
            return {'error': 'FILE_NOT_FOUND', 'file': story}
        command = [self.get_executable(), story]
        return {'command': command}
