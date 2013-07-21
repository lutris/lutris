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
import os.path

from lutris.runners.runner import Runner


# pylint: disable=C0103
class linux(Runner):
    """Runs native games"""
    def __init__(self, config=None):
        super(linux, self).__init__()
        self.platform = "Linux games"
        self.ld_preload = None
        self.game_path = None
        self.game_options = [
            {
                "option": "exe",
                "type": "file_chooser",
                "default_path": "game_path",
                "label": "Executable"
            },
            {
                "option": "args",
                "type": "string",
                "label": "Arguments"
            },
            {
                "option": "ld_preload",
                "type": "file_chooser",
                "label": "Preload library"
            },
            {
                "option": "ld_library_path",
                "type": "directory_chooser",
                "label": "Add directory to LD_LIBRARY_PATH"
            }
        ]
        self.runner_options = []
        self.config = config

    def is_installed(self):
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def get_game_path(self):
        return os.path.dirname(self.config['game']['exe'])

    def play(self):
        """ Run native game. """
        game_config = self.config.get('game')
        if not game_config:
            return {'error': 'INVALID_CONFIG'}

        executable = game_config.get("exe")
        if not os.path.exists(executable):
            return {'error': 'FILE_NOT_FOUND', 'file': executable}

        launch_info = {}

        self.game_path = self.get_game_path()
        launch_info['game_path'] = self.game_path

        ld_preload = game_config.get('ld_preload')
        if ld_preload:
            launch_info['ld_preload'] = ld_preload

        ld_library_path = game_config.get('ld_library_path')
        if ld_library_path:
            launch_info['ld_library_path'] = ld_library_path

        command = []
        command.append("./%s" % os.path.basename(executable))

        args = game_config.get('args', "")
        for arg in args.split():
            command.append(arg)
        launch_info['command'] = command
        return launch_info
