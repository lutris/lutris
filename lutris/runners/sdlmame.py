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
""" Mame module """

import os
import subprocess

from lutris.runners.runner import Runner


# pylint: disable=C0103
class sdlmame(Runner):
    """Runs arcade games with SDLMame"""
    def __init__(self, settings=None):
        """ Mame initialization """
        super(sdlmame, self).__init__()
        self.executable = "mame"
        self.machine = "Arcade"
        self.game_options = [{"option": "rom",
                              "type":"file_chooser",
                              "label":"Rom file"}]
        self.runner_options = [{"option":"windowed",
                                "type":"bool",
                                "label":"Windowed"}]
        self.settings = settings

    def play(self):
        """ Launch the game. """
        settings = self.settings
        fullscreen = True
        romdir = os.path.dirname(settings["game"]["rom"])
        rom = os.path.basename(settings["game"]["rom"])
        mameconfigdir = os.path.join(os.path.expanduser("~"), ".mame")
        if "sdlmame" in settings.config:
            if "windowed" in settings["sdlmame"]:
                fullscreen = not settings["sdlmame"]["windowed"]
        if not os.path.exists(os.path.join(mameconfigdir, "mame.ini")):
            try:
                os.makedirs(mameconfigdir)
            except OSError:
                pass
            os.chdir(mameconfigdir)
            subprocess.Popen([self.executable, "-createconfig"],
                             stdout=subprocess.PIPE)
            os.chdir(romdir)
        arguments = []
        if not fullscreen:
            arguments = arguments + ["-window"]
        return {'command': [self.executable,
                "-inipath", mameconfigdir,
                "-skip_gameinfo",
                "-rompath", romdir, rom] + arguments}
