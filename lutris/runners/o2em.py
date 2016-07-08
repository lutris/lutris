# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner


class o2em(Runner):
    human_name = "O2EM"
    description = "Magnavox Oyssey² Emulator"
    platform = "Magnavox Odyssey 2, Phillips Videopac+"
    bios_path = os.path.expanduser("~/.o2em/bios")

    checksums = {
        'o2rom': "562d5ebf9e030a40d6fabfc2f33139fd",
        'c52': "f1071cdb0b6b10dde94d3bc8a6146387",
        'jopac': "279008e4a0db2dc5f1c048853b033828",
        'g7400': "79008e4a0db2dc5f1c048853b033828",
    }

    bios_choices = [
        ("Magnavox Odyssey2", "o2rom"),
        ("Phillips C52", "c52"),
        ("Phillips Videopac+", "g7400"),
        ("Brandt Jopac", "jopac")
    ]
    controller_choices = [
        ("Disable", "0"),
        ("Arrows keys and right shift", "1"),
        ("W,S,A,D,SPACE", "2"),
        ("Joystick", "3")
    ]
    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": "ROM file",
        "default_path": 'game_path',
        'help': ("The game data, commonly called a ROM image.")
    }]
    runner_options = [
        {
            "option": "bios",
            "type": "choice",
            "choices": bios_choices,
            "label": "Bios",
            'default': 'o2rom',
        },
        {
            "option": "controller1",
            "type": "choice",
            "choices": controller_choices,
            "label": "First controller",
            'default': '2',
        },
        {
            "option": "controller2",
            "type": "choice",
            "choices": controller_choices,
            "label": "Second controller",
            'default': '1',
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            'default': False,
        },
        {
            "option": "scanlines",
            "type": "bool",
            "label": "Scanlines display style",
            'default': False,
            'help': ("Activates a display filter adding scanlines to imitate "
                     "the displays of yesteryear.")
        }
    ]

    def install(self, version=None, downloader=None, callback=None):
        def on_runner_installed(*args):
            if not os.path.exists(self.bios_path):
                os.makedirs(self.bios_path)
            if callback:
                callback()
        super(o2em, self).install(version, downloader, on_runner_installed)

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'o2em/o2em')

    def play(self):
        arguments = ["-biosdir=%s" % self.bios_path]

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")

        if self.runner_config.get("scanlines"):
            arguments.append("-scanlines")

        if "controller1" in self.runner_config:
            arguments.append("-s1=%s" % self.runner_config["controller1"])
        if "controller2" in self.runner_config:
            arguments.append("-s2=%s" % self.runner_config["controller2"])
        rom_path = self.game_config.get('main_file') or ''
        if not os.path.exists(rom_path):
            return {'error': 'FILE_NOT_FOUND', 'file': rom_path}
        romdir = os.path.dirname(rom_path)
        romfile = os.path.basename(rom_path)
        arguments.append("-romdir=%s/" % romdir)
        arguments.append(romfile)
        return {'command': [self.get_executable()] + arguments}
