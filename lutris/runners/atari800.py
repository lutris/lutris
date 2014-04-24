# -*- coding:Utf-8 -*-
"""Runner for Atari 800 (and other early Atari consoles)"""
import os.path
import logging

from lutris.runners.runner import Runner
from lutris.util.display import get_resolutions


# pylint: disable=C0103
class atari800(Runner):
    """ Runs Atari800 games """
    package = "atari800"
    executable = "atari800"
    platform = "Atari 8bit computers"
    atarixl_url = (
        "http://kent.dl.sourceforge.net/project/atari800/"
        "ROM/Original%20XL%20ROM/xf25.zip"
    )
    description = "Atari 400,800 and XL emulator."
    bios_checksums = {
        "xlxe_rom": "06daac977823773a3eea3422fd26a703",
        "basic_rom": "0bac0c6a50104045d902df4503a4c30b",
        "osa_rom": "",
        "osb_rom": "a3e8d617c95d08031fe1b20d541434b2",
        "5200_rom": ""
    }
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "Rom File"
        }
    ]
    try:
        screen_resolutions = [(resolution, resolution)
                              for resolution in get_resolutions()]
    except OSError:
        screen_resolutions = []

    runner_options = [
        {
            "option": "bios_path",
            "type": "directory_chooser",
            "label": "Bios Path"
        },
        {
            "option": "machine",
            "type": "choice",
            "choices": (
                ("Emulate Atari 800", "atari"),
                ("Emulate Atari 800 XL", "xl"),
                ("Emulate Atari 320 XE (Compy Shop)", "320xe"),
                ("Emulate Atari 320 XE (Rambo)", "rambo"),
                ("Emulate Atari 5200", "5200")
            ),
            "label": "Machine"
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        },
        {
            "option": "resolution",
            "type": "choice",
            "choices": screen_resolutions,
            "label": "Fullscreen resolution"
        }
    ]

    def is_installed(self):
        """Checks if atari800 is installed"""
        is_installed = super(atari800, self).is_installed()
        if is_installed is False:
            return False
        if not os.path.exists(os.path.join(os.path.expanduser('~'),
                              '.config/lutris/runnerfiles/xf25.zip')):
            return False

    def find_good_bioses(self):
        """ Check for correct bios files """
        good_bios = {}
        for filename in os.listdir(self.bios_path):
            real_hash = self.md5sum(os.path.join(self.bios_path, filename))
            for bios_file in self.bios_checksums.keys():
                if real_hash == self.bios_checksums[bios_file]:
                    logging.debug("%s Checksum : OK", filename)
                    good_bios[bios_file] = filename
        return good_bios

    def play(self):
        arguments = [self.executable]
        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        else:
            arguments.append("-windowed")

        if self.runner_config.get("resolution"):
            width, height = self.runner_config["resolution"].split('x')
            arguments += ["-width", "%s" % width, "-height", "%s" % height]

        bios_path = self.runner_config.get("bios_path")
        if not os.path.exists(bios_path):
            return {'error': 'NO_BIOS'}

        if self.runner_config("machine"):
            arguments.append("-%s" % self.runner_config["machine"])

        rom = self.settings["game"].get("rom")
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND', 'file': rom}
        good_bios = self.find_good_bioses()
        for bios in good_bios.keys():
            arguments.append("-%s" % bios)
            bios_path = os.path.join(self.bios_path, good_bios[bios])
            arguments.append("\"%s\"" % bios_path)
        arguments.append("\"%s\"" % rom)
        return {"command": arguments}
