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
        self.platform = "Amiga"
        self.is_installable = True
        self.uae_options = {}
        control_choices = [("Mouse", "mouse"), ("Joystick 1", "joy0"),
                           ("Joystick 2", "joy1"),  ("Keyboard 1", "kbd1"),
                           ("Keyboard 2", "kbd2"),  ("Keyboard 3", "kbd3")]
        amiga_choices = [
            {"A500": "Amiga 500 with 512 KB chip RAM and 512 KB slow RAM, "
                     "defaulting to Kickstart 1.3"},
            {"A500+": "Amiga 500+ with 1 MB chip RAM, "
                      "defaulting to Kickstart 2.04"},
            {"A600": "Amiga 600 with 1 MB chip RAM, "
                     "defaulting to Kickstart 2.05"},
            {"A1000": "Amiga 1000 with 512 KB chip RAM, "
                      "defaulting to Kickstart 1.2"},
            {"A1200": "Amiga 1200 with 2 MB chip RAM, "
                      "defaulting to Kickstart 3.1"},
            {"A1200/020": "Amiga 1200 but with 68020 processor instead of "
                          "68ec020 – allows the use of Zorro III RAM"},
            {"A4000/040": "Amiga 4000 with 2 MB chip RAM and a 68040 "
                          "processor running as fast as possible, "
                          "defaulting to Kickstart 3.1"},
            {"CD32": "CD32 unit"},
            {"CDTV": "Commodore CDTV unit"},
        ]
        self.game_options = [{
            "option": "disk",
            "type": "multiple",
            "label": "Floppies"
        }]

        self.runner_options = [
            {
                "option": "kickstart_rom_file",
                "label": "Rom Path",
                "type": "file"
            },
            {
                "option": "x11.floppy_path",
                "label": "Floppy path",
                "type": "directory_chooser"
            },
            {
                "option": "use_gui",
                "label": "Show UAE gui",
                "type": "bool"
            },

            {
                "option": "gfx_show_leds_fullscreen",
                "label": "Show LEDs",
                "type": "bool"
            },
            {
                "option": "machine",
                "label": "Type of Amiga",
                "type": "one_choice",
                "choices": [(choice.values()[0], choice.keys()[0])
                            for choice in amiga_choices]
            },
            {
                "option": "joyport0",
                "label": "Player 1 Control",
                "type": "one_choice",
                "choices": control_choices
            },
            {
                "option": "joyport1",
                "label": "Player 2 Control",
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
        inserted_disks = 0
        runner = self.__class__.__name__
        drives = self.settings[runner].get("nr_floppies")
        disks = []
        floppies = self.settings['game'].get('disk', [])
        for drive, disk in enumerate(floppies):
            disks.append('-s')
            disks.append('floppy%s' % str(drive))
            disks.append(os.path.join(self.settings["game"]["disk"][drive]))
            inserted_disks = inserted_disks + 1
            if inserted_disks == drives:
                break
        return disks

    def get_params(self):
        raise ValueError
        runner = self.__class__.__name__
        if runner in self.settings.config:
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
                if config_key in self.settings[runner]:
                    value = self.settings[runner][config_key]
                    if type(value) == bool:
                        value = str(value).lower()
                    self.uae_options.update({config_key: value})
            if "machine" in self.settings[runner]:
                machine = self.settings[runner]["machine"].replace(" ",
                                                                   "").lower()
                if machine == "A1200":
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
        params = []
        for option in self.uae_options:
            params.append('-s')
            params.append(option + "=" + self.uae_options[option])
        return self.uae_options

    def play(self):
        params = self.get_params()
        disks = self.insert_floppies()
        command = [self.executable]
        for param in params:
            command.append(param)
        for disk in disks:
            command.append(disk)
        return command
