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

class vavoom(Runner):
    def __init__(self,settings=None):
        self.executable = "vavoom"
        self.package = None
        self.description = "Runs games based on the Doom engine like Doom, Hexen, Heretic"
        self.machine = "Games based on the Doom engine"
        if settings:
            self.wad = settings["main"]["wad"]

        
    
    def play(self):
        return [self.executable,self.gfxmode,self.wad]