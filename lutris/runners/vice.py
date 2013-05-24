
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

'''Runner for MSX games'''

from lutris.runners.runner import Runner


# pylint: disable=C0103
class vice(Runner):
    """Commodore Emulator"""
    def __init__(self, settings=None):
        '''Constructor'''
        super(vice, self).__init__()
        self.package = "vice"
        self.executable = "x64"
        self.platform = "Commodore 64"
        self.arguments = []
        self.game_options = [{
            "option": "main_file",
            "type": "file_chooser",
            "label": "Disk File"
        }]
        self.runner_options = [
            {
                "option": "joy",
                "type": "bool",
                "label": "Use joysticks"
            },
            {
                "option": "fullscreen",
                "type": "bool",
                "label": "Fullscreen"
            },
            {
                "option": "double",
                "type": "bool",
                "label": "Double Size"
            }
        ]

        if settings:
            if "fullscreen" in settings["vice"]:
                if settings["vice"]["fullscreen"]:
                    self.arguments = self.arguments + ["-fullscreen"]
            if "double" in settings["vice"]:
                if settings["vice"]["double"]:
                    self.arguments = self.arguments + ["-VICIIdsize"]
            if "joy" in settings["vice"]:
                if settings["vice"]["joy"]:
                    self.arguments = self.arguments + \
                        ["-joydev2", "4", "-joydev1", "5"]
            self.arguments = self.arguments + \
                ["\"%s\"" % settings['game']['main_file']]

    def play(self):
        return [self.executable] + self.arguments
