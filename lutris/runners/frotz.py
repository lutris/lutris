# -*- coding: utf-8 -*-
# It is pitch black. You are likely to be eaten by a grue.

import os
from lutris import settings
from lutris.runners.runner import Runner


class frotz(Runner):
    """Z-code emulator for text adventure games such as Zork"""
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
            "label": "Story File"
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'frotz/frotz')

    def play(self):
        story = self.settings["game"]["story"]
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED'}
        if not os.path.exists(story):
            return {'error': 'FILE_NOT_FOUND', 'file': story}
        command = ['x-terminal-emulator', '-e', "\"" + self.executable,
                   "\"" + story + "\"\""]
        return {'command': command}
