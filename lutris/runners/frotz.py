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

""" Runner for text based adventure games """

import os

from lutris.runners.runner import Runner


# pylint: disable=C0103
class frotz(Runner):
    '''Runner for z-code games such as Zork'''
    def __init__(self, settings=None):
        '''Constructor'''
        super(frotz, self).__init__()
        self.package = "frotz"
        self.executable = "frotz"
        self.machine = "Z-Code"
        self.is_installable = True
        self.description = "Z Code interpreter (Infocom interactive fictions)"
        self.game_options = [{
            "option": "story",
            "type": "file_chooser",
            "label": "Story File"
        }]
        self.runner_options = []
        if settings:
            self.story = settings["game"]["story"]

    def play(self):
        """ Run the game """
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED'}
        if not os.path.exists(self.story):
            return {'error': 'FILE_NOT_FOUND', 'file': self.story}
        command = [
            'x-terminal-emulator',
            '-e', "\"" + self.executable,
            "\"" + self.story + "\"\""
        ]
        return command
