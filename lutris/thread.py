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
from lutris.util.process import Process

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
        logger.debug('Running thread from %s', self.path)

    def attach_thread(self, thread):
        """Attach child process that need to be killed on game exit"""
        self.attached_threads.append(thread)

    def run(self):
        """Run the thread"""
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

    def iter_children(self, process, topdown=True):
        for child in process.children:
            if topdown:
                yield child
            gen = self.iter_children(child)
            for c in gen:
                yield c
            if not topdown:
                yield child

    def set_stop_command(self, func):
        self.stop_func = func

    def stop(self):
        if hasattr(self, 'stop_func'):
            self.stop_func()
            return
        for thread in self.attached_threads:
            thread.stop()
        for process in self.iter_children(topdown=False):
            process.kill()

    def watch_children(self):
        """pokes at the running process"""
        process = Process(self.rootpid)
        print "ROOT: {} {}".format(process.pid, process.name)
        for child in self.iter_children(process):
            if "steamwebhelper" in child.cmdline:
                continue
            print "{}\t{}\t{}".format(child.pid,
                                      child.state,
                                      child.name)
        return True
