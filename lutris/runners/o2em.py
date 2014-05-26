# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner


class o2em(Runner):
    """Magnavox Oyssey² Emulator"""
    package = "o2em"
    executable = "o2em"
    platform = "Magnavox Odyssey 2, Phillips Videopac+"

    tarballs = {
        'i386': None,
        'x64': "o2em-1.18-x86_64.tar.gz",
    }
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
        "label": "Rom File",
        "default_path": 'game_path',
    }]
    runner_options = [
        {
            "option": "bios",
            "type": "choice",
            "choices": bios_choices,
            "label": "Bios"
        },
        {
            "option": "controller1",
            "type": "choice",
            "choices": controller_choices,
            "label": "First controller"
        },
        {
            "option": "controller2",
            "type": "choice",
            "choices": controller_choices,
            "label": "Second controller"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        {
            "option": "scanlines",
            "type": "bool",
            "label": "Scanlines"
        }
    ]

    def install(self):
        super(o2em, self).install()
        bios_path = os.path.expanduser("~/.o2em/bios")
        if not os.path.exists(bios_path):
            os.makedirs(bios_path)

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'o2em/o2em')

    def play(self):
        bios_path = os.path.join(os.path.expanduser("~"), ".o2em/bios/")
        arguments = ["-biosdir=\"%s\"" % bios_path]

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")

        if self.runner_config.get("scanlines"):
            arguments.append("-scanlines")

        if "controller1" in self.runner_config:
            arguments.append("-s1=%s" % self.runner_config["controller1"])
        if "controller2" in self.runner_config:
            arguments.append("-s2=%s" % self.runner_config["controller2"])
        rom_path = self.settings["game"].get("main_file", '')
        if not os.path.exists(rom_path):
            return {'error': 'FILE_NOT_FOUND', 'file': rom_path}
        romdir = os.path.dirname(rom_path)
        romfile = os.path.basename(rom_path)
        arguments.append("-romdir=\"%s\"/" % romdir)
        arguments.append("\"%s\"" % romfile)
        return {'command': [self.get_executable()] + arguments}
