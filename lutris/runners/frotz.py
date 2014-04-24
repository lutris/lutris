# -*- coding: utf-8 -*-
# It is pitch black. You are likely to be eaten by a grue.

import os
from lutris.runners.runner import Runner


class frotz(Runner):
    """Runner for z-code games such as Zork"""
    package = "frotz"
    executable = "frotz"
    platform = "Z-Code"
    is_installable = True
    description = "Z Code interpreter (Infocom interactive fictions)"
    game_options = [
        {
            "option": "story",
            "type": "file",
            "label": "Story File"
        }
    ]

    def play(self):
        story = self.settings["game"]["story"]
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED'}
        if not os.path.exists(story):
            return {'error': 'FILE_NOT_FOUND', 'file': story}
        command = ['x-terminal-emulator', '-e', "\"" + self.executable,
                   "\"" + story + "\"\""]
        return {'command': command}
