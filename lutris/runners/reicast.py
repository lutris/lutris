# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner


class reicast(Runner):
    human_name = "Reicast"
    description = "Sega Dreamcast emulator"
    platform = "Sega Dreamcast"

    game_options = [{
        'option': 'iso',
        'type': 'file',
        'label': 'Disc image file',
        'help': ("The game data.\n"
                 "Supported formats: ISO, CDI")
    }]

    runner_options = []

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'reicast/reicast')

    def play(self):
        iso = self.game_config.get('iso')
        command = [self.get_executable(), iso]
        return {'command': command}
