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
from lutris.util import system

HEARTBEAT_DELAY = 5000  # Number of milliseconds between each heartbeat


class LutrisThread(threading.Thread):
    """Runs the game in a separate thread"""
    def __init__(self, command, path="/tmp", rootpid=None):
        """Thread init"""
        threading.Thread.__init__(self)
        self.command = command
        self.path = path
        self.game_process = None
        self.return_code = None
        self.rootpid = rootpid or os.getpid()
        self.pid = 99999
        self.stdout = []
        self.attached_threads = []
        self.prerun_children = set()
        self.watched_children = set()
        logger.debug('Running thread from %s', self.path)

    def attach_thread(self, thread):
        """Attach child process that need to be killed on game exit"""
        self.attached_threads.append(thread)

    def run(self):
        """Run the thread"""
        self.prerun_children = self.get_children_pids()
        logger.debug("Thread running: %s", self.command)
        GLib.timeout_add(HEARTBEAT_DELAY, self.watch_children)
        self.game_process = subprocess.Popen(self.command, shell=True,
                                             bufsize=1,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             cwd=self.path)
        for line in iter(self.game_process.stdout.readline, ''):
            self.stdout.append(line)
            sys.stdout.write(line)

    def get_children(self):
        return system.get_child_tree(os.getpid())['children']

    def get_children_pids(self):
        """Return a set containing all children pids launched by main process"""
        return set([child['pid'] for child in self.get_children()])

    def set_stop_command(self, func):
        self.stop_func = func

    def stop(self):
        if hasattr(self, 'stop_func'):
            self.stop_func()
            return
        for thread in self.attached_threads:
            thread.stop()
        pid = self.game_process.pid + 1
        logger.debug('SIGKILL %d', pid)
        try:
            os.kill(pid, SIGKILL)
        except OSError:
            logger.error("Could not kill PID %s", pid)
        self.pid = None

    def watch_children(self):
        """pokes at the running process"""
        self.watched_children = self.get_children_pids() - self.prerun_children
        self.pid = self.game_process.pid
        self.return_code = self.game_process.poll()
        if self.return_code is not None:
            logger.debug("Game quit")
            self.pid = None
            return False
        return True
