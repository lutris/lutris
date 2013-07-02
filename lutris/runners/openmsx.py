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

""" Runner for MSX games """

from lutris.runners.runner import Runner


# pylint: disable=C0103
class openmsx(Runner):
    """Runner for MSX games"""
    def __init__(self, settings=None):
        """Constructor"""
        super(openmsx, self).__init__()
        self.package = "openmsx"
        self.executable = "openmsx"
        self.platform = "MSX"
        self.description = "MSX Emulator"
        self.game_options = [
            {
                "option": "main_file",
                "type": "file_chooser",
                "label": "ROM File"
            }
        ]
        self.runner_options = []
        if settings:
            self.rom = settings["game"]["main_file"]

    def play(self):
        """Run MSX game"""
        command = [self.executable, "\"%s\"" % self.rom]
        return {'command': command}
