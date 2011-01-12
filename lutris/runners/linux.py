import logging
import os.path
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
import os
import stat

class linux(Runner):
    def __init__(self,settings=None):
        self.description = "Runs native games"
        self.machine = "Linux games"
        self.is_installable = True
        self.ld_preload = None
        self.installer_options = [{"option": "installer","type": "single","label": "Executable"}]

        self.game_options = [ {"option": "exe", "type":"single", "label":"Executable"},
                              {"option": "args", "type": "string", "label": "Arguments"},
                              {"option": "ld_preload", "type": "single", "label": "Preload libray"}]
        self.runner_options = []
        if settings:
            self.executable = settings["game"]["exe"]
            if 'args' in settings['game']:
                self.args = settings['game']['args']
            else:
            	self.args = None
            if 'ld_preload' in settings['game']:
            	self.ld_preload = settings['game']['ld_preload']

    def get_install_command(self,installer_path):
        #Check if installer exists
        if not os.path.exists(installer_path):
            raise IOError

        #Check if script is executable and make it executable if not
        if not os.access(installer_path,os.X_OK):
           logging.debug("%s is not executable, setting it executable")
           os.chmod(installer_path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)

        return  "x-terminal-emulator -e %s" % installer_path

    def is_installed(self):
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def play(self):
        self.game_path = os.path.dirname(self.executable)
        if not os.path.exists(self.executable):
            return {'error': 'FILE_NOT_FOUND', 'file': self.executable }
        command = []
        if self.ld_preload:
        	command.append("LD_PRELOAD=%s " % self.ld_preload)
        command.append("./%s"  % os.path.basename(self.executable))
        if self.args:
        	for arg in self.args.split():
        		command.append(arg)

        return {'command': command }
