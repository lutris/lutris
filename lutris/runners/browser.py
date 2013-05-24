# -*- coding:Utf-8 -*-
""" Runner for browser games """
from lutris.runners.runner import Runner


# pylint: disable=C0103
class browser(Runner):
    """Runner for browser games"""

    def __init__(self, settings=None):
        """Constructor"""
        super(browser, self).__init__()
        self.package = "x-www-browser"
        self.executable = "x-www-browser"
        self.platform = "Web Browser"
        self.description = "Run games in the browser"
        self.game_options = [
            {
                "option": "main_file",
                "type": "string",
                "label": "URL"
            }
        ]
        self.runner_options = [
            {
                'option': 'browser',
                'type': "file_chooser",
                'label': "Web Browser"
            }
        ]
        if settings:
            self.settings = settings
            runner_settings = settings["browser"]
            self.browser_exec = runner_settings.get('browser', self.executable)

    def play(self):
        """Run a browser game"""
        url = self.settings["game"]["main_file"]
        command = [self.browser_exec, "\"%s\"" % url]
        return command
