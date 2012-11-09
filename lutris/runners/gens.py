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

""" Runner for Sega Genesis games """

import subprocess

from os import mkdir
from os.path import exists, join, expanduser

from lutris.runners.runner import Runner
from lutris.gui.common import DownloadDialog
from lutris.settings import CACHE_DIR


# pylint: disable=C0103
class gens(Runner):
    '''Runner for Sega Genesis games'''
    def __init__(self, settings=None):
        '''Constructor'''
        super(gens, self).__init__()
        self.package = 'gens-gs'
        self.executable = 'gens'
        self.machine = 'Sega Genesis'
        self.description = 'Sega Genesis emulator.'
        self.game_options = [{
            'option': 'rom',
            'type':'file_chooser',
            'label':  'Rom File'
        }]
        self.runner_options = [
            {
                'option': 'fullscreen',
                'type':'bool',
                'label': 'Fullscreen'
            },
            {
                'option': 'quickexit',
                'type': 'bool',
                'label': 'Exit emulator with Esc'
            }
        ]
        if settings:
            if 'fullscreen' in settings['gens']:
                if settings['gens']['fullscreen']:
                    self.arguments = self.arguments + ['--fs']
                else:
                    self.arguments = self.arguments + ['--window']
            if 'quickexit' in settings['gens']:
                if settings['gens']['quickexit']:
                    self.arguments = self.arguments + ['--quickexit']
            if 'rom' in settings['game']:
                self.rom = settings['game']['rom']

    def install(self):
        """Downloads deb package and installs it"""
        dest = join(CACHE_DIR, 'gens-gs.deb')
        package = 'http://segaretro.org/images/7/75/Gens_2.16.7_i386.deb'
        dialog = DownloadDialog(package, dest)
        dialog.run()
        subprocess.Popen(["software-center", dest],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)

    def play(self):
        """ Run the game """
        plugins_dir = join(expanduser('~'), '.gens', 'plugins')
        if not exists(plugins_dir):
            mkdir(plugins_dir)
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        if not exists(self.rom):
            return {'error': 'FILE_NOT_FOUND', 'file': self.rom}
        self.arguments = self.arguments + ["--game \"%s\"" % self.rom]
        command = [self.executable] + self.arguments
        return {"command": command}
