import os.path
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

import os
import subprocess
from lutris.runners.runner import Runner

class sdlmame(Runner):
    def __init__(self,settings=None):
        self.executable = "sdlmame"
        self.package = "sdlmame"
        self.description = "Runs arcade games with SDLMame"
        self.machine = "Arcade"
        self.is_installable = False
        self.fullscreen = True
        self.game_options = [{"option": "rom", "type":"single","label":"Rom file"}]
        self.runner_options = [{"option":"windowed","type":"bool","label":"Windowed"}]
                
        if settings:
            self.romdir = os.path.dirname(settings["game"]["rom"])
            self.rom = os.path.basename(settings["game"]["rom"])
            self.mameconfigdir = os.path.join(os.path.expanduser("~"),".mame")
            if "sdlmame" in settings.config:
                if "windowed" in settings["sdlmame"]:
                    self.fullscreen = not settings["sdlmame"]["windowed"]

    
    def play(self):
        if not os.path.exists(os.path.join(self.mameconfigdir,"mame.ini")):
            try:
                os.makedirs(self.mameconfigdir)
            except OSError:
                pass
            os.chdir(self.mameconfigdir)
            subprocess.Popen([self.executable,"-createconfig"],stdout=subprocess.PIPE).communicate()[0]
        os.chdir(self.romdir)
        arguments = []
        if not self.fullscreen:
            arguments = arguments + ["-window"]
        return [self.executable,"-inipath",self.mameconfigdir,"-skip_gameinfo","-rompath",self.romdir,self.rom] + arguments