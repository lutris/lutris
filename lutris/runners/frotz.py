# -*- coding: utf-8 -*-
# It is pitch black. You are likely to be eaten by a grue.

import os
from lutris.runners.runner import Runner


class frotz(Runner):
    human_name = "Frotz"
    description = "Z-code emulator for text adventure games such as Zork."
    platforms = ["Z-Machine"]
    runner_executable = 'frotz/frotz'

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

    def play(self):
        story = self.game_config.get('story') or ''
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED'}
        if not os.path.exists(story):
            return {'error': 'FILE_NOT_FOUND', 'file': story}
        command = [self.get_executable(), story]
        return {'command': command}
