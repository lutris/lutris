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

from lutris.runners.wine import wine
import os

class nulldc(Runner):
    """Runner for the Dreamcast emulator NullDC
    
    Since there is no good Linux emulator out there, we have to use a Windows 
    emulator. It runs pretty well.
    
    NullDC is now OpenSource ! Somebody please port it to Linux.
    
    Download link : http://nulldc.googlecode.com/files/nullDC_104_r50.7z
    
    TODO: implement joy2key or use Lutris' own version
    """
    
    def __init__(self,settings=None):
        """Initialize NullDC
        
        TODO: Remove hardcoded stuff
        """
        self.description = "Runs Dreamcast games with nullDC emulator"
        self.machine = "Sega Dreamcast"
        
        self.is_installable = False
        
        self.depends = "wine"
        self.nulldc_path = "/mnt/seagate/games/nullDC/"
        self.executable = "nullDC_1.0.3_mmu.exe"
        self.gamePath = "/mnt/seagate/games/Soul Calibur [NTSC-U]/"
        self.gameIso = "disc.gdi"
        self.args = ""
        self.game_options = [{"option": "file",
                              "type":"single", 
                              "name":"iso",
                              "label":"Disc image"}]
        self.runner_options = [{"option":"fullscreen",
                                "type":"bool",
                                "name":"fullscreen",
                                "label":"Fullscreen"}]

    def is_installed(self):
        if not self.depends():
            return False
        nulldc_path = self.get_nulldc_path()
        if not os.path.exists(nulldc_path):
            return False
        else:
            return True
    
    def get_nulldc_path(self):
        """ Return the full path for the NullDC executable.
        
        TODO: Load from config
        """
        return os.path.join(self.nulldc_path, self.executable)

    def play(self):
        os.chdir(self.nulldc_path)
        #-config ImageReader:DefaultImage="[rompath]/[romfile]"

        path = self.gamePath + self.gameIso
        path = path.replace("/", "\\")
        path = 'Z:' + path

        command = ["WINEDEBUG=-all",
                   "wine",
                   self.get_nulldc_path(),
                   "-config",
                   " ImageReader:DefaultImage=\"" + path + "\"",
                   "-config", "drkpvr:Fullscreen.Enabled=1"]
        
        return command