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

""" Linux runner """

import os
import stat
import os.path

from lutris.util.log import logger
from lutris.runners.runner import Runner


# pylint: disable=C0103
class linux(Runner):
    """Runs native games"""
    def __init__(self, config=None):
        super(linux, self).__init__()
        self.platform = "Linux games"
        self.ld_preload = None
        self.game_path = None
        self.installer_options = [{"option": "installer",
                                   "type": "file_chooser",
                                   "label": "Executable"}]
        self.game_options = [{"option": "exe",
                              "type": "file_chooser",
                              "default_path": "game_path",
                              "label": "Executable"},
                             {"option": "args",
                              "type": "string",
                              "label": "Arguments"},
                             {"option": "ld_preload",
                              "type": "file_chooser",
                              "label": "Preload library"}]
        self.runner_options = []
        self.config = config

    def get_install_command(self, installer_path):
        """ Launch install script (usually .bin or .sh) """
        #Check if installer exists
        if not os.path.exists(installer_path):
            raise IOError

        #Check if script is executable and make it executable if not
        if not os.access(installer_path, os.X_OK):
            logger.debug("%s is not executable, setting it executable")
            os.chmod(installer_path,
                     stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)

        return "x-terminal-emulator -e %s" % installer_path

    def is_installed(self):
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def play(self):
        """Run native game."""
        logger.debug("Launching Linux game")
        game_config = self.config.get('game')
        if not game_config:
            return {'error': 'INVALID_CONFIG'}

        executable = game_config.get("exe")
        args = game_config.get('args', "")
        self.ld_preload = game_config.get('ld_preload', None)
        if not os.path.exists(executable):
            return {'error': 'FILE_NOT_FOUND', 'file': executable}
        self.game_path = os.path.dirname(executable)
        command = []
        if self.ld_preload:
            command.append("LD_PRELOAD=%s " % self.ld_preload)
        command.append("./%s" % os.path.basename(executable))
        for arg in args.split():
            command.append(arg)
        logger.debug("Linux runner args: %s" % command)
        return {'command': command}
