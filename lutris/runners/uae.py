# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
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

""" Runs Amiga games with UAE"""

import os
from lutris.runners.runner import Runner


# pylint: disable=C0103
class uae(Runner):

    """Run Amiga games with UAE"""
    def __init__(self, settings=None):
        super(uae, self).__init__()
        self.package = "uae"
        self.executable = "uae"
        self.machine = "Amiga"
        self.is_installable = True
        self.uae_options = {}
        control_choices = [("Mouse", "mouse"), ("Joystick 1", "joy0"),
                           ("Joystick 2", "joy1"),  ("Keyboard 1", "kbd1"),
                           ("Keyboard 2", "kbd2"),  ("Keyboard 3", "kbd3")]
        amiga_choices = [("Amiga 500", "amiga500"),
                         ("Amiga 1200", "amiga1200")]
        self.game_options = [{
            "option": "disk",
            "type":"multiple",
            "label":"Floppies"
        }]

        self.runner_options = [
            {
                "option": "kickstart_rom_file",
                "label": "Rom Path",
                "type": "file_chooser"
            },
            {
                "option": "x11.floppy_path",
                "label":"Floppy path",
                "type": "directory_chooser"
            },
            {
                "option": "use_gui",
                "label": "Show UAE gui",
                "type":"bool"
            },
            {
                "option": "gfx_fullscreen_amiga",
                "label": "Fullscreen (F12 + s to Switch)",
                "type":"bool"
            },
            {
                "option": "gfx_show_leds_fullscreen",
                "label": "Show LEDs",
                "type":"bool"
            },
            {
                "option": "machine",
                "label":"Type of Amiga",
                "type":"one_choice",
                "choices": amiga_choices
            },
            {
                "option": "joyport0",
                "label": "Player 1 Control",
                "type": "one_choice",
                "choices": control_choices
            },
            {
                "option": "joyport1",
                "label":"Player 2 Control",
                "type": "one_choice",
                "choices": control_choices
            },
            {
                "option": "nr_floppies",
                "label": "Number of disk drives",
                "type": "range",
                "min": "1", "max": "4"
            }
        ]

        self.settings = settings

    def insert_floppies(self):
        #Insert floppies
        if "disk" in self.settings.config["game"]:
            drives = self.settings["uae"]["nr_floppies"]
            disks = len(self.settings["game"]["disk"])
            inserted_disks = 0
            for drive in range(0, drives):
                self.uae_options.update({
                    "floppy%s" % str(drive): "\"%s\"" %
                    os.path.join(self.settings["game"]["disk"][drive])
                })
                inserted_disks = inserted_disks + 1
                if inserted_disks == disks:
                    break

    def handle_settings(self):
        if "uae" in self.settings.config:
            config_keys = [
                "kickstart_rom_file",
                "gfx_fullscreen_amiga",
                "gfx_show_leds_fullscreen",
                "unix.rom_path",
                "unix.floppy_path",
                "joyport0",
                "joyport1",
                "use_gui",
            ]

            for config_key in config_keys:
                if config_key in self.settings["uae"]:
                    value = self.settings["uae"][config_key]
                    if type(value) == bool:
                        value = str(value).lower()
                    self.uae_options.update({config_key: value})
            if "machine" in self.settings["uae"]:
                machine = self.settings["uae"]["machine"].replace(" ",
                                                                  "").lower()
                if machine == "amiga1200":
                    amiga_settings = {
                        "chipset": "aga",
                        "cpu_speed": "15",
                        "cpu_type": "68020",
                        "chipmem_size": "4",
                        "fastmem_size": "2"
                    }
                else:
                    #Load at least something by default !
                    amiga_settings = {
                        "chipset": "ocs",
                        #CPU Speed is supposed to be set on "real"
                        #for Amiga 500 speed, but it's simply too fast...
                        #"cpu_speed":"real",
                        "cpu_speed": "15",
                        "cpu_type": "68000",
                        "chipmem_size": "1",
                        "fastmem_size": "0",
                        "bogomem_size": "2"
                    }
                self.uae_options.update(amiga_settings)
        #Hardcoded stuff
        #If you have some better settings or have any reason that this
        #shouldn't be hardcoded, please let me know
        sound_settings = {
            "sound_output": "normal",
            "sound_bits": "16",
            "sound_frequency": "44100",
            "sound_channels": "stereo",
            "sound_interpolation": "rx"
        }
        gfx_settings = {
            "gfx_width_windowed": "640",
            "gfx_height_windowed": "512",
            "gfx_linemode": "double",
            "gfx_center_horizontal": "simple",
            "gfx_center_vertical": "simple"
        }
        self.uae_options.update(sound_settings)
        self.uae_options.update(gfx_settings)

    def play(self):
        self.handle_settings()
        self.insert_floppies()
        command = [self.executable]
        for option in self.uae_options:
            command.append("-s")
            command.append(option + "=" + self.uae_options[option])
        return command
