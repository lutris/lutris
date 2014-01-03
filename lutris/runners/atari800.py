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
            "type": "file_chooser",
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
            "type": "one_choice",
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
            "type": "one_choice",
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
        """ Run the game. """

        if "fullscreen" in self.settings["atari800"]:
            if self.settings["atari800"]["fullscreen"]:
                self.arguments = self.arguments + ["-fullscreen"]
            else:
                self.arguments = self.arguments + ["-windowed"]

        if "resolution" in self.settings["atari800"]:
            resol = self.settings["atari800"]["resolution"]
            width = resol[:resol.find("x")]
            height = resol[resol.find("x") + 1:]
            self.arguments += ["-width", "%s" % str(width),
                               "-height", "%s" % str(height)]

        if "bios_path" in self.settings["atari800"]:
            self.bios_path = self.settings["atari800"]["bios_path"]
        else:
            self.error_messages += ["Bios path not set."]

        if "machine" in self.settings["atari800"]:
            self.arguments += ["-%s" % self.settings["atari800"]["machine"]]

            self.rom = self.settings["game"].get("rom")
            if not self.rom:
                self.error_messages += ["No disk image given."]
        good_bios = self.find_good_bioses()
        for bios in good_bios.keys():
            self.arguments += ["-%s" % bios,
                               "\"%s\"" % os.path.join(self.bios_path,
                                                       good_bios[bios])]
        self.arguments = self.arguments + ["\"%s\"" % self.rom]
        command = [self.executable] + self.arguments
        return {"command": command, "error_messages": self.error_messages}
