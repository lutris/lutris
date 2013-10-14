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

import os
import sys
import threading
import subprocess
from signal import SIGKILL

from gi.repository import GLib

from lutris.util.log import logger


class LutrisThread(threading.Thread):
    """Runs the game in a separate thread"""
    def __init__(self, command, path="/tmp", killswitch=None):
        """Thread init"""
        threading.Thread.__init__(self)
        self.command = command
        self.path = path
        self.output = ""
        self.game_process = None
        self.return_code = None
        self.pid = 99999
        self.child_processes = []
        if type(killswitch) == type(str()) and not os.path.exists(killswitch):
            # Prevent setting a killswitch to a file that doesn't exists
            self.killswitch = None
        else:
            self.killswitch = killswitch

    def attach_thread(self, thread):
        """Attach child process that need to be killed on game exit"""
        self.child_processes.append(thread)

    def run(self):
        """Run the thread"""
        logger.debug("Thread running: %s", self.command)
        GLib.timeout_add(2000, self.poke_process)
        self.game_process = subprocess.Popen(self.command, shell=True,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             cwd=self.path)
        self.output = self.game_process.stdout
        line = "\n"
        while line:
            line = self.game_process.stdout.read(80)
            sys.stdout.write(line)

    def get_process_status(self):
        with open("/proc/%s/status" % self.pid) as status_file:
            for line in status_file.read():
                if line.startswith("State:"):
                    return line.split()[1]

    def set_stop_command(self, func):
        # TODO
        logger.debug(func)

    def stop(self):
        if self.stop_func:
            self.stop_func()
        for child in self.child_processes:
            child.stop()
        pid = self.game_process.pid + 1
        logger.debug('SIGKILL %d', pid)
        try:
            os.kill(pid, SIGKILL)
        except OSError:
            logger.error("Could not kill PID %s", pid)
        self.pid = None
        self.kill()

    def poke_process(self):
        """pokes at the running process"""
        if not self.game_process:
            logger.debug("game not running")
            return True
        else:
            if self.killswitch and not os.path.exists(self.killswitch):
                # How are we sure that pid + 1 is actually the game process ?
                return False
        self.pid = self.game_process.pid
        self.return_code = self.game_process.poll()
        if self.return_code is not None:
            logger.debug("Game quit")
            self.pid = None
            return False
        return True
