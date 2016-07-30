# -*- coding: utf-8 -*-
import re
import os
from collections import Counter
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import joypad


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

    def __init__(self, config=None):
        super(reicast, self).__init__(config)

        self._joypads = None

        self.runner_options = [
            {
                'option': 'fullscreen',
                'type': 'bool',
                'label': 'Fullscreen',
                'default': False,
            },
            {
                'option': 'device_id_1',
                'type': 'choice',
                'label': 'Joypad 1',
                'choices': self.get_joypads(),
                'default': '-1'
            },
            {
                'option': 'device_id_2',
                'type': 'choice',
                'label': 'Joypad 2',
                'choices': self.get_joypads(),
                'default': '-1'
            },
            {
                'option': 'device_id_3',
                'type': 'choice',
                'label': 'Joypad 3',
                'choices': self.get_joypads(),
                'default': '-1'
            },
            {
                'option': 'device_id_4',
                'type': 'choice',
                'label': 'Joypad 4',
                'choices': self.get_joypads(),
                'default': '-1'
            }
        ]

    def get_joypads(self):
        """Return list of joypad in a format usable in the options"""
        if self._joypads:
            return self._joypads
        joypad_list = [('No joystick', '-1')]
        joypad_devices = joypad.get_joypads()
        name_counter = Counter([j[1] for j in joypad_devices])
        name_indexes = {}
        for (dev, joy_name) in joypad_devices:
            dev_id = re.findall(r'(\d+)', dev)[0]
            if name_counter[joy_name] > 1:
                if joy_name not in name_indexes:
                    index = 1
                else:
                    index = name_indexes[joy_name] + 1
                name_indexes[joy_name] = index
            else:
                index = 0
            if index:
                joy_name += " (%d)" % index
            joypad_list.append((joy_name, dev_id))
        self._joypads = joypad_list
        return joypad_list

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'reicast/reicast.elf')

    def play(self):
        iso = self.game_config.get('iso')
        fullscreen = '1' if self.runner_config.get('fullscreen') else '0'
        command = [
            self.get_executable(),
            "-config", "config:image={}".format(iso),
            "-config", "x11:fullscreen={}".format(fullscreen)
        ]
        return {'command': command}
