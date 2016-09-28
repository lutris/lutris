# -*- coding: utf-8 -*-

import os

from lutris.runners.runner import Runner
from lutris.util import datapath
from lutris import pga

DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')

class electron(Runner):
    human_name = "Electron"
    description = "Runs browser games"
    platform = "Web based games"
    description = "Runs browser games in an Electron window"
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": "Full address (URL)",
            'help': ("The full address of the game's web page.")
        }
    ]
    runner_executable = 'electron/bin/electron-runner'
    system_options_override = [
        {
            'option': 'disable_runtime',
            'default': True,
        }
    ]

    def play(self):
        url = self.game_config.get('main_file')
        if not url:
            return {'error': 'CUSTOM',
                    'text': ("The web address is empty, \n"
                             "verify the game's configuration."), }

        game_data = pga.get_game_by_field(self.config.game_config_id, 'configpath')

        icon = datapath.get_icon_path(game_data.get('slug'))
        if not os.path.exists(icon):
            icon = DEFAULT_ICON

        return {'command': [self.get_executable(), url, icon]}
