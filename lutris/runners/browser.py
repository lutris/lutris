# -*- coding: utf-8 -*-
from lutris.runners.runner import Runner


class browser(Runner):
    """Runner for browser games"""
    executable = "xdg-open"
    platform = "Web Browser"
    description = "Run games in the browser"
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": "URL"
        }
    ]
    runner_options = [
        {
            'option': 'browser',
            'type': "file",
            'label': "Web Browser"
        }
    ]

    def is_installed(self):
        return True

    def play(self):
        self.browser_exec = self.runner_config.get('browser', self.executable)
        url = self.settings["game"]["main_file"]
        return {'command': [self.browser_exec, "\"%s\"" % url]}
