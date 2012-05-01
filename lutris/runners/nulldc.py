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

""" Runner for Dreamcast games """

import os
from lutris.runners.wine import wine
from lutris.gui.common import DirectoryDialog
from lutris.config import LutrisConfig


# pylint: disable=C0103
class nulldc(wine):
    """Runner for the Dreamcast emulator NullDC

    Since there is no good Linux emulator out there, we have to use a Windows
    emulator. It runs pretty well.

    NullDC is now OpenSource ! Somebody please port it to Linux.
    The open source NullDC version (1.0.4) doesn't work with wine !

    Download link : http://nulldc.googlecode.com/files/nullDC_104_r50.7z

    """

    def __init__(self, settings=None):
        """Initialize NullDC

        TODO: Remove hardcoded stuff

        joy2key $(xwininfo -root -tree  | grep nullDC | grep -v VMU |\
                awk '{print $1}') \
                -X  -rcfile ~/.joy2keyrc \
                -buttons y a b x c r l r o s -axis Left Right Up Down
        """
        super(nulldc, self).__init__(settings)
        self.description = "Runs Dreamcast games with nullDC emulator"
        self.machine = "Sega Dreamcast"

        self.is_installable = False

        self.depends = "wine"
        config = LutrisConfig(runner=self.__class__.__name__)
        self.nulldc_path = config.get_path()
        self.executable = "nullDC_1.0.3_nommu.exe"
        self.gamePath = "/mnt/seagate/games/Soul Calibur [NTSC-U]/"
        self.gameIso = "disc.gdi"
        self.args = ""
        self.game_options = [{
            'option': 'iso',
            'type': 'single',
            'name': 'iso',
            'label': 'Disc image'
        }]
        self.runner_options = self.runner_options + [{
            'option': 'fullscreen',
            'type': 'bool',
            'name': 'fullscreen',
            'label': 'Fullscreen'
        }]
        if settings:
            self.settings = settings

    def install(self):
        dlg = DirectoryDialog('Where is NullDC located ?')
        config = LutrisConfig(runner=self.__class__.__name__)
        config.runner_config = {'system': {'game_path': dlg.folder}}
        config.save(config_type='runner')

    def is_installed(self):
        if not self.check_depends():
            return False
        nulldc_path = self.get_nulldc_path()
        if not nulldc_path or not os.path.exists(nulldc_path):
            return False
        else:
            return True

    def get_nulldc_path(self):
        """ Return the full path for the NullDC executable."""
        if not self.nulldc_path:
            return ""
        else:
            return os.path.join(self.nulldc_path, self.executable)

    def play(self):
        #-config ImageReader:DefaultImage="[rompath]/[romfile]"
        path = self.settings['game']['iso']
        path = path.replace("/", "\\")
        path = 'Z:' + path

        command = ["wine", self.get_nulldc_path(),
                   "-config", "ImageReader:DefaultImage=\"%s\"" % path]

        self.check_regedit_keys()  # From parent wine runner
        return {'command': command,
                'joy2key': {'buttons': 'y a b x c r l r o s',
                            'window': 'nullDC',
                            'notwindow': 'VMU'}}
