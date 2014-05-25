# -*- coding: utf-8 -*-
import os
from lutris import settings
from lutris.runners.runner import Runner


class o2em(Runner):
    """Magnavox Oyssey² Emulator"""
    package = "o2em"
    executable = "o2em"
    platform = "Odyssey 2"

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
        "option": "rom",
        "type": "file",
        "label": "Rom File"
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
        tarball = self.get_tarball()
        if tarball:
            self.download_and_extract(tarball)

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'o2em/o2em')

    def play(self):
        bios_path = os.path.join(os.path.expanduser("~"), ".o2em/bios/")
        arguments = ["-biosdir=\"%s\"" % bios_path]

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")

        if self.runner_config.get("scanlines"):
            arguments.append("-scanlines")

        if "first_controller" in self.runner_config:
            arguments.append("-s1=%s" % self.runner_config["controller1"])
        if "second_controller" in self.runner_config:
            arguments.append("-s2=%s" % self.runner_config["controller2"])
        romdir = os.path.dirname(self.settings["game"]["rom"])
        romfile = os.path.basename(self.settings["game"]["rom"])
        self.arguments.append("-romdir=\"%s\"/" % romdir)
        self.arguments.append("\"%s\"" % romfile)
        return {'command': [self.executable] + self.arguments}
