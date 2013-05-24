
# -*- coding:Utf-8 -*-
###############################################################################
## Lutris, get_resolutions
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

"""Runner for Atari 800 (and other early Atari consoles)"""

import os.path
import logging

from lutris.runners.runner import Runner
from lutris.desktop_control import get_resolutions


# pylint: disable=C0103
class atari800(Runner):
    """ Runs Atari800 games """
    def __init__(self, settings=None):
        """Constructor"""
        super(atari800, self).__init__()
        self.package = "atari800"
        self.executable = "atari800"
        self.platform = "Atari 8bit computers"
        self.atarixl_url = (
            "http://kent.dl.sourceforge.net/project/atari800/"
            "ROM/Original%20XL%20ROM/xf25.zip"
        )
        self.description = "Atari 400,800 and XL emulator."
        self.bios = None
        self.bios_checksums = {
            "xlxe_rom": "06daac977823773a3eea3422fd26a703",
            "basic_rom": "0bac0c6a50104045d902df4503a4c30b",
            "osa_rom": "",
            "osb_rom": "a3e8d617c95d08031fe1b20d541434b2",
            "5200_rom": ""
        }

        self.game_options = [
            {
                "option": "main_file",
                "type": "file_chooser",
                "label": "Rom File"
            }
        ]

        # protip : list comprehensions !
        self.screen_resolutions = []
        resolutions_available = get_resolutions()
        for resolution in resolutions_available:
            self.screen_resolutions = self.screen_resolutions + \
                [(resolution, resolution)]

        machine_choices = (
            ("Emulate Atari 800", "atari"),
            ("Emulate Atari 800 XL", "xl"),
            ("Emulate Atari 320 XE (Compy Shop)", "320xe"),
            ("Emulate Atari 320 XE (Rambo)", "rambo"),
            ("Emulate Atari 5200", "5200")
        )

        self.runner_options = [
            {
                "option": "bios_path",
                "type": "directory_chooser",
                "label": "Bios Path"
            },
            {
                "option": "machine",
                "type": "one_choice",
                "choices": machine_choices,
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
                "choices": self.screen_resolutions,
                "label": "Fullscreen resolution"
            }
        ]

        if settings:
            if "fullscreen" in settings["atari800"]:
                if settings["atari800"]["fullscreen"]:
                    self.arguments = self.arguments + ["-fullscreen"]
                else:
                    self.arguments = self.arguments + ["-windowed"]

            if "resolution" in settings["atari800"]:
                resol = settings["atari800"]["resolution"]
                width = resol[:resol.find("x")]
                height = resol[resol.find("x") + 1:]
                self.arguments += ["-width", "%s" % str(width),
                                   "-height", "%s" % str(height)]

            if "bios_path" in settings["atari800"]:
                self.bios_path = settings["atari800"]["bios_path"]
            else:
                self.error_messages += ["Bios path not set."]

            if "machine" in settings["atari800"]:
                self.arguments += ["-%s" % settings["atari800"]["machine"]]

            self.rom = settings["game"].get("rom")
            if not self.rom:
                self.error_messages += ["No disk image given."]

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
        good_bios = self.find_good_bioses()
        for bios in good_bios.keys():
            self.arguments += ["-%s" % bios,
                               "\"%s\"" % os.path.join(self.bios_path,
                                                       good_bios[bios])]
        self.arguments = self.arguments + ["\"%s\"" % self.rom]
        command = [self.executable] + self.arguments
        return_val = {"command": command,
                      "error_messages": self.error_messages}
        return return_val
