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

from runner import Runner
from lutris.desktop_control import LutrisDesktopControl
import os
import os.path
import logging

class hatari(Runner):
    '''Runner for intellivision games'''

    def __init__(self,settings = None):
        '''Constructor'''
        super(hatari,self).__init__()
        self.package = "hatari"
        self.executable = "hatari"
        self.machine = "Atari ST computers"
        self.is_installable = True
        self.description = "AtariST emulator."

        self.game_options = [ {"option": "disk-a", "type":"single", "label": "Floppy Disk A"},
                              {"option": "disk-b", "type":"single", "label": "Floppy Disk B"},
                            ]
                              
        self.screen_resolutions = []
        desktop_control = LutrisDesktopControl()
        resolutions_available = desktop_control.get_resolutions()
        for resolution in resolutions_available:
            self.screen_resolutions = self.screen_resolutions + [(resolution,resolution)]

        joystick_choices = [('None','none'),('Keyboard','keys'),('Joystick','real')]

        self.runner_options = [{"option": "bios_file", "type":"file_chooser", "label": "Bios File (TOS.img)"},
                               {"option": "fullscreen", "type":"bool", "label": "Fullscreen"},
                               {"option": "zoom", "type": "bool", "label": "Double ST low resolution"},
                               {"option": "borders", "type": "bool", 'label': 'Add borders to display'},
                               {"option": "status", "type": "bool", 'label': 'Display status bar'},
                               {"option": "joy1", "type": "one_choice", "label": "Joystick 1", "choices": joystick_choices },
                               {"option": "joy2", "type": "one_choice", "label": "Joystick 2", "choices": joystick_choices },
                             ]

        if settings:
            if "fullscreen" in settings["hatari"]:
                if settings["hatari"]["fullscreen"]:
                    self.arguments = self.arguments + ["--fullscreen"]
                else:
                    self.arguments = self.arguments + ["--window"]
            if "zoom" in settings["hatari"]:
                if settings["hatari"]["zoom"]:
                    self.arguments = self.arguments + ["--zoom 2"]
                else:
                    self.arguments = self.arguments + ["--zoom 1"]
            if 'borders' in settings['hatari'] and settings["hatari"]["borders"]:
                self.arguments = self.arguments + ['--borders true']
            else:
                self.arguments = self.arguments + ['--borders false']

            if 'status' in settings['hatari'] and settings["hatari"]["status"]:
                self.arguments = self.arguments + ['--statusbar true']
            else:
                self.arguments = self.arguments + ['--statusbar false']
            if "joy1" in settings["hatari"]:
                self.arguments = self.arguments + ["--joy0 "+settings["hatari"]['joy1']]
            if "joy2" in settings["hatari"]:
                self.arguments = self.arguments + ["--joy1 "+settings["hatari"]['joy2']]
                
            if "bios_file" in settings["hatari"]:
                self.arguments = self.arguments + ["--tos "+settings["hatari"]["bios_file"]]
            else:
                self.error_messages = self.error_messages + [ "TOS path not set."]
            if "disk-a" in settings['game']:
                self.diska = settings['game']['disk-a']


    def play(self):
        self.arguments = self.arguments + [ "--disk-a \"%s\"" % self.diska ]
        command = [self.executable] + self.arguments
        return_val = { "command": command ,"error_messages": self.error_messages}
        return return_val
