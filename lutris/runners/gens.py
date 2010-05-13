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

from lutris.runners.runner import Runner
import os.path

class gens(Runner):
    '''Runner for intellivision games'''

    def __init__(self,settings = None):
        '''Constructor'''
        super(gens,self).__init__()
        self.package = "gens"
        self.executable = "gens"
        self.machine = "Sega Genesis"
        self.is_installable = True
        self.description = "AtariST emulator."

        self.game_options = [ {"option": "rom", "type":"single", "label": "Rom File"}]

        self.runner_options = [{"option": "fullscreen", "type":"bool", "label": "Fullscreen"},
                               {"option": "quickexit", "type": "bool", "label": "Exit emulator with Esc"}]

        if settings:
            if "fullscreen" in settings["gens"]:
                if settings["gens"]["fullscreen"]:
                    self.arguments = self.arguments + ["--fs"]
                else:
                    self.arguments = self.arguments + ["--window"]
            if "quickexit" in settings["gens"]:
                if settings["gens"]["quickexit"]:
                    self.arguments = self.arguments + ["--quickexit"]

            if "rom" in settings['game']:
                self.rom = settings['game']['rom']

    def play(self):
        self.arguments = self.arguments + [ "--game \"%s\"" % self.rom ]
        command = [self.executable] + self.arguments
        return_val = { "command": command ,"error_messages": self.error_messages}
        return return_val