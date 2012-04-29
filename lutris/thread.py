#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010, 2011 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Threading module, used to launch games while keeping Lutris operational.
"""

import sys
import logging
import gobject
import threading
import subprocess
from os.path import exists
from signal import SIGKILL

from os import kill


class LutrisThread(threading.Thread):
    """Runs the game in a separate thread"""
    def __init__(self, command, path, killswitch=None):
        """Thread init"""
        threading.Thread.__init__(self)
        self.command = command
        self.path = path
        self.output = ""
        self.game_process = None
        self.return_code = None
        self.pid = 99999
        if type(killswitch) == type(str()) and not exists(killswitch):
            # Prevent setting a killswitch to a file that doesn't exists
            self.killswitch = None
        else:
            self.killswitch = killswitch

    def run(self):
        gobject.timeout_add(2000, self.poke_process)
        logging.debug(self.command)
        self.game_process = subprocess.Popen(self.command, shell=True,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             cwd=self.path)
        self.output = self.game_process.stdout
        line = "\n"
        while line:
            line = self.game_process.stdout.read(80)
            sys.stdout.write(line)

    def poke_process(self):
        """pokes at the running process"""
        if not self.game_process:
            logging.debug("game not running")
            return True
        else:
            if self.killswitch is not None and not exists(self.killswitch):
                # How are we sure that pid + 1 is actually the game process ?
                kill(self.game_process.pid + 1, SIGKILL)
                self.pid = None
                return False
        self.pid = self.game_process.pid
        self.return_code = self.game_process.poll()
        if self.return_code is not None:
            logging.debug("Game quit")
            self.pid = None
            return False
        return True
