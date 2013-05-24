# -*- coding:Utf-8 -*-
# It is pitch black. You are likely to be eaten by a grue.
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

"""Runner for stella Atari 2600 emulator"""

from lutris.runners.runner import Runner


class stella(Runner):
    """Atari 2600 games emulator"""

    def __init__(self, settings=None):
        """Constructor"""
        super(stella, self).__init__()
        self.package = "stella"
        self.executable = "stella"
        self.platform = "Atari 2600"
        self.game_options = [{
            "option": "cart",
            "type": "file_chooser",
            "label": "Cartridge"
        }]
        self.runner_options = []
        if settings:
            self.cart = settings["game"]["cart"]

    def play(self):
        command = ['stella', "\"%s\"" % self.cart]
        return {'command': command}
