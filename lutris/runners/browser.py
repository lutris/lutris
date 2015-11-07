# -*- coding: utf-8 -*-
from lutris.runners.runner import Runner


class browser(Runner):
    human_name = "Browser"
    description = "Runs browser games"
    executable = "xdg-open"
    platform = "Web based games"
    description = "Runs games in the browser"
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
        if not url:
            return {'error': 'CUSTOM',
                    'text': ("The web address is empty, \n"
                             "verify the game's configuration."), }
        return {'command': [self.browser_exec, url]}
