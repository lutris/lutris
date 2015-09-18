# -*- coding: utf-8 -*-
from lutris.runners.runner import Runner


class browser(Runner):
    """Runner for browser games"""
    human_name = "Browser"
    executable = "xdg-open"
    platform = "Web based games"
    description = "Run games in the browser"
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": "Full address (URL)",
            'help': ("The full address of the game's web page.")
        }
    ]
    runner_options = [
        {
            'option': 'browser',
            'type': "file",
            'label': "Custom web browser",
            'help': ("Select the executable of a browser on your system. \n"
                     "If left blank, Lutris will launch your default browser.")
        }
    ]
    system_options_override = [
        {
            'option': 'disable_runtime',
            'default': True,
        }
    ]

    def is_installed(self):
        return True

    def play(self):
        self.browser_exec = self.runner_config.get('browser', self.executable)
        url = self.game_config.get('main_file')
        return {'command': [self.browser_exec, url]}
