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

""" Runner for MS Dos games """

import os
from lutris.util.log import logger
from lutris.runners.runner import Runner


# pylint: disable=C0103
class dosbox(Runner):
    """Runner for MS Dos games"""
    def __init__(self, settings=None):
        """Constructor"""
        super(dosbox, self).__init__()
        self.package = "dosbox"
        self.executable = "dosbox"
        self.platform = "MS DOS"
        self.description = "DOS Emulator"
        self.game_options = [
            {
                "option": "main_file",
                "type": "file_chooser",
                "label": "EXE File"
            },
            {
                "option": "config_file",
                "type": "file_chooser",
                "label": "Configuration file"
            }
        ]
        self.runner_options = []
        self.settings = settings

    def play(self):
        """ Run the game """
        logger.debug(self.settings)
        self.exe = self.settings["game"]["main_file"]
        self.game_path = os.path.dirname(self.exe)
        if not os.path.exists(self.exe):
            return {'error': "FILE_NOT_FOUND", 'file': self.exe}
        if self.exe.endswith(".conf"):
            exe = ["-conf", self.exe]
        else:
            exe = [self.exe]
        if "config_file" in self.settings["game"]:
            params = ["-conf", self.settings["game"]["config_file"]]
        else:
            params = []
        return {'command': [self.executable] + params + exe}
