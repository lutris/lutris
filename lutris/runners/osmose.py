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

class osmose(Runner):
    '''Runner for Sega Master System games'''

    def __init__(self,settings = None):
        '''Constructor'''
        self.package = "osmose"
        self.executable = "osmose"
        self.machine = "Sega Master System"
        #osmose is not yet available as a package  in Debian and Ubuntu,
        #it requires some packaging
        self.is_installable = False

        self.description = "Sega Master System Emulator"

        self.game_options = [{
            'option': 'rom',
            'type': 'single',
            'label': 'Rom File'
        }]
        self.runner_options = [
            {'option': 'fullscreen', 'type': 'bool', 'label': 'Fullscreen'},
            {'option': 'joy', 'type': 'bool', 'label': 'Use joystick'}
        ]
        self.arguments = []
        if settings:
            self.settings = settings

    def play(self):
        if 'fullscreen' in self.settings['osmose']:
            if self.settings['osmose']['fullscreen']:
                self.arguments = self.arguments + ['-fs','-bilinear']
        if 'joy' in self.settings["osmose"]:
            if self.settings['osmose']['joy']:
                self.arguments = self.arguments + ['-joy']

        self.rom = self.settings['game']['rom']
        self.arguments = self.arguments + ["\"" + self.rom + "\""]

        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        if not os.path.exists(self.rom):
            return {'error': 'FILE_NOT_FOUND',
                    'file': self.rom}

        return { 'command': [self.executable] + self.arguments }

