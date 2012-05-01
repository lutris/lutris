# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009, 2010 Mathieu Comandon strycore@gmail.com
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
from lutris.gui.common import NoticeDialog

# pylint: disable=C0103
class dolphin(Runner):
    """Runner for the Gamecube / Wii emulator Dolphin

    Code repository: http://code.google.com/p/dolphin-emu/
    Download link : http://dolphin.jcf129.com/dolphin-2.0.i686.tar.bz2

    """
    def __init__(self):

        self.ppa = "ppa:glennric/dolphin-emu"
        self.package = "dolphin-emu"
        self.executable = "dolphin"
        self.machine = "Gamecube, Wii"
        self.description = "Emulator for Nintendo Gamecube and Wii games"

    def install(self):
        NoticeDialog('Please activate the PlayDeb reposiories in order to install Dolphin')
        super(dolphin, self).install()









