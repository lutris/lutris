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
import os.path


class mupen64plus(Runner):
    '''Runner for Sega Genesis games'''

    def __init__(self, settings=None):
        super(mupen64plus, self).__init__()
        self.package = 'mupen64plus'
        self.executable = 'mupen64plus'
        self.machine = "Nintendo 64"
        self.arguments = ['--nogui']
        self.is_installable = True
        self.description = "Nintendo 64 emulator"

        self.game_options = [{
            'option': 'rom',
            'type':'single',
            'label': 'Rom File'
        }]

        self.runner_options = [{
            'option': 'fullscreen',
            'type':'bool',
            'label': 'Fullscreen'
        }]

        if settings:
            if 'fullscreen' in settings['mupen64plus']:
                if settings['mupen64plus']['fullscreen']:
                    self.arguments.append('--fullscreen')

            if 'rom' in settings['game']:
                self.rom = settings['game']['rom']

    def play(self):
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        if not os.path.exists(self.rom):
            return {'error': 'FILE_NOT_FOUND', 'file': self.rom}

        self.arguments = self.arguments + ["\"%s\"" % self.rom]
        command = [self.executable] + self.arguments

        return {'command': command}
