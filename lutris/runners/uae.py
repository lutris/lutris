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

import os
from lutris.runners.runner import Runner

class uae(Runner):
    def __init__(self,settings = None):
        self.package = "uae"
        self.executable = "uae"
        self.description = "Runs Amiga games with UAE"
        self.machine = "Amiga"
        self.uae_options = {}
        self.is_installable = False
        control_choices = [("Mouse","mouse"), ("Joystick 1","joy0"),
                           ("Joystick 2","joy1"),  ("Keyboard 1","kbd1"),
                           ("Keyboard 2","kbd2"),  ("Keyboard 3","kbd3")]
        amiga_choices = [("Amiga 500","amiga500"),
                         ("Amiga 1200","amiga1200")]
        self.game_options = [ {"option": "disk", "type":"multiple", "label":"Floppies"}]

        self.runner_options = [
          {"option": "x11.rom_path", "label": "Rom Path", "type":"directory_chooser"},
          {"option": "x11.floppy_path", "label":"Floppy path", "type": "directory_chooser"},
          {"option": "use_gui", "label":"Show UAE gui","type":"bool"},
          {"option": "gfx_fullscreen_amiga", "label": "Fullscreen (F12 + s to Switch)", "type":"bool"},
          {"option": "gfx_show_leds_fullscreen","label": "Show LEDs", "type":"bool"},
          {"option": "machine", "label":"Type of Amiga","type":"one_choice","choices": amiga_choices},
          {"option": "joyport0", "label":"Player 1 Control", "type": "one_choice", "choices": control_choices },
          {"option": "joyport1", "label":"Player 2 Control", "type": "one_choice", "choices": control_choices },
          {"option": "nr_floppies", "label":"Number of disk drives", "type": "range", "min": "1", "max": "4"} ]

        if settings:
            if "uae" in settings.config:
                config_keys = ["gfx_fullscreen_amiga","gfx_show_leds_fullscreen",
                "unix.rom_path","unix.floppy_path","joyport0","joyport1","use_gui"]

                for config_key in config_keys:
                    if config_key in settings["uae"]:
                        value = settings["uae"][config_key]
                        if type(value) == bool:
                            value = str(value).lower()
                        self.uae_options.update({config_key: value})
                if "machine" in settings["uae"]:
                    if settings["uae"]["machine"].replace(" ","").lower() == "amiga1200":
                        amiga_settings = {"kickstart_rom_file":"\""+os.path.join(settings["uae"]["x11.rom_path"],"kick31.rom")+"\"",
                                              "chipset":"aga",
                                              "cpu_speed":"15",
                                              "cpu_type":"68020",
                                              "chipmem_size":"4",
                                              "fastmem_size":"2"
                                          }
                    #if settings["uae"]["machine"].replace(" ","").lower() == "amiga500":
                    #Load at least something by default !
                    else:
                        rom_file = "kick13.rom"
                        amiga_settings = {"kickstart_rom_file": "\""+os.path.join(settings["uae"]["x11.rom_path"],rom_file)+"\"",
                                              "chipset":"ocs",
                                              #CPU Speed is supposed to be set on "real"
                                              #for Amiga 500 speed, but it's simply too fast...
                                              #"cpu_speed":"real",
                                              "cpu_speed":"15",
                                              "cpu_type":"68000",
                                              "chipmem_size":"1",
                                              "fastmem_size":"0",
                                              "bogomem_size":"2"}
                    self.uae_options.update(amiga_settings)
            #Hardcoded stuff
            #If you have some better settings or have any reason that this
            #shouldn't be hardcoded, please let me know
            sound_settings = {"sound_output": "normal",
                              "sound_bits": "16",
                              "sound_frequency":"44100",
                              "sound_channels":"stereo",
                              "sound_interpolation":"rx"}
            gfx_settings = {"gfx_width_windowed":"640",
                            "gfx_height_windowed":"512",
                            "gfx_linemode":"double",
                            "gfx_center_horizontal":"simple",
                            "gfx_center_vertical":"simple"}
            self.uae_options.update(sound_settings)
            self.uae_options.update(gfx_settings)

            #Insert floppies
            if "disk" in settings.config["game"]:
                drives = settings["uae"]["nr_floppies"]
                disks = len(settings["game"]["disk"])
                inserted_disks = 0
                for drive in range(0,drives):
                    self.uae_options.update({"floppy"+str(drive) : "\""+
                    #settings["uae"]["unix.floppy_path"]
                    os.path.join(settings["game"]["disk"][drive])+"\""})
                    inserted_disks = inserted_disks +1
                    if inserted_disks == disks:
                        break

    def get_game_options(self):
        return {"file":self.file_options , "options":self.runner_options}


    def play(self):
        command = [self.executable]
        for option in self.uae_options:
            command.append("-s")
            command.append(option+"="+self.uae_options[option])
        return command

