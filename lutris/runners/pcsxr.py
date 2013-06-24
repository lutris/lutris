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
""" pcsx runner """

from lutris.runners.runner import Runner


#pylint: disable=C0103
class pcsxr(Runner):
    """PlayStation emulator"""
    def __init__(self, settings=None):
        super(pcsxr, self).__init__()
        self.executable = "pcsxr"
        self.package = "pcsxr"
        self.is_installable = True
        self.platform = "Playstation"
        self.game_options = [{"option": "iso",
                              "type": "file_chooser",
                              "label": "iso"}]
        self.runner_options = []
        #Load settings
        if settings:
            self.iso = settings["game"]["iso"]

    def play(self):
        """Run Playstation game"""
        return [self.executable, " -nogui -cdfile \"" + self.iso + "\" -runcd"]
