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

"""Runner for Sega Master System"""

import os

from lutris.runners.runner import Runner


# pylint: disable=C0103
class osmose(Runner):
    """Sega Master System Emulator"""
    def __init__(self, settings=None):
        '''Constructor'''
        super(osmose, self).__init__()
        self.package = "osmose"
        self.executable = "osmose"
        self.machine = "Sega Master System"
        #osmose is not yet available as a package  in Debian and Ubuntu,
        #it requires some packaging
        self.game_options = [{
            'option': 'rom',
            'type': 'file_chooser',
            'label': 'Rom File'
        }]
        self.runner_options = [
            {'option': 'fullscreen', 'type': 'bool', 'label': 'Fullscreen'},
            {'option': 'joy', 'type': 'bool', 'label': 'Use joystick'}
        ]
        self.settings = settings

    def play(self):
        """Run Sega Master System game"""
        arguments = []
        if 'fullscreen' in self.settings['osmose']:
            if self.settings['osmose']['fullscreen']:
                arguments = arguments + ['-fs', '-bilinear']
        if 'joy' in self.settings["osmose"]:
            if self.settings['osmose']['joy']:
                arguments = arguments + ['-joy']

        rom = self.settings['game']['rom']
        arguments = arguments + ["\"" + rom + "\""]

        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND',
                    'file': rom}
        return {'command': [self.executable] + arguments}
