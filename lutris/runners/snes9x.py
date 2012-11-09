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

""" Super Nintendo runner """

from lutris.runners.runner import Runner


# pylint: disable=C0103
class snes9x(Runner):
    """Runs Super Nintendo games with Snes9x"""
    def __init__(self, settings=None):
        """It seems that the best snes emulator around it snes9x-gtk
        zsnes has no 64bit port
        """
        super(snes9x, self).__init__()
        self.executable = "snes9x-gtk"
        self.package = None
        self.machine = "Super Nintendo"
        self.is_installable = True
        self.game_options = [{"option": "rom",
                              "type": "file_chooser",
                              "label": "ROM"}]
        self.runner_options = [{
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen"
        }]
        if settings:
            self.rom = settings["game"]["rom"]

    def play(self):
        return [self.executable, "\"%s\"" % self.rom]
