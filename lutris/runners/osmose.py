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

from lutris import settings
from lutris.runners.runner import Runner


# pylint: disable=C0103
class osmose(Runner):
    """Sega Master System Emulator"""

    package = "osmose"
    executable = "osmose"
    platform = "Sega Master System"

    tarballs = {
        'i386': "osmose-0.9.96-i386.tar.gz",
        'x64': "osmose-0.9.96-x64.tar.gz"
    }

    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'Rom File'
        }
    ]

    runner_options = [
        {'option': 'fullscreen', 'type': 'bool', 'label': 'Fullscreen'},
        {'option': 'joy', 'type': 'bool', 'label': 'Use joystick'}
    ]

    def is_installed(self):
        if os.path.exists(self.get_executable()):
            return True
        else:
            return super(osmose, self).is_installed()

    def install(self):
        tarball = self.get_tarball()
        if tarball:
            self.download_and_extract(tarball)

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'osmose/osmose')

    def play(self):
        """Run Sega Master System game"""
        arguments = []
        if 'fullscreen' in self.settings['osmose']:
            if self.settings['osmose']['fullscreen']:
                arguments = arguments + ['-fs', '-bilinear']
        if 'joy' in self.settings["osmose"]:
            if self.settings['osmose']['joy']:
                arguments = arguments + ['-joy']

        rom = self.settings['game']['main_file']
        arguments = arguments + ["\"%s\"" % rom]

        if not os.path.exists(rom):
            return {'error': 'FILE_NOT_FOUND',
                    'file': rom}
        return {'command': [self.get_executable()] + arguments}
