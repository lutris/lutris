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

'''Runner for intellivision games'''

from lutris.runners.runner import Runner
import os.path


# pylint: disable=C0103
class jzintv(Runner):
    """Intellivision Emulator"""

    def __init__(self, settings=None):
        '''Constructor'''
        super(jzintv, self).__init__()
        self.package = "jzintv"
        self.executable = "jzintv"
        self.machine = "Intellivision"
        #jzintv is not yet available as a package  in Debian and Ubuntu,
        #it requires some packaging
        self.is_installable = False
        self.game_options = [{
            "option":"rom",
            "type":"single",
            "label":"Rom File"
        }]
        self.runner_options = [
            {
                "option": "bios_path",
                "type": "directory_chooser",
                "label": "Bios Path"
            },
            {
                "option": "fullscreen",
                "type": "bool",
                "label":"Fullscreen"
            }
        ]
        self.arguments = []
        if settings:
            if "fullscreen" in settings["jzintv"]:
                if settings["jzintv"]["fullscreen"]:
                    self.arguments = self.arguments + ["-f"]
            if "bios_path" in settings["jzintv"]:
                self.arguments += ["--execimg=\"%s/exec.bin\"" % \
                        settings["jzintv"]["bios_path"]]
                self.arguments += ["--gromimg=\"%s/grom.bin\"" % \
                        settings["jzintv"]["bios_path"]]
            else:
                self.error_message = "Bios path not set"
            romdir = os.path.dirname(settings["game"]["rom"])
            romfile = os.path.basename(settings["game"]["rom"])
            self.arguments += ["--rom-path=\"%s/\"" % romdir]
            self.arguments += ["\"%s\"" % romfile]

    def play(self):
        command = [self.executable] + self.arguments
        return command
