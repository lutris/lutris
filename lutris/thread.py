#!/usr/bin/python
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

import logging
import threading
import subprocess
import gobject

from lutris.runners.cedega import cedega

class LutrisThread(threading.Thread):
    """Runs the game in a separate thread"""

    def __init__(self, command, path):
        """Thread init"""

        threading.Thread.__init__(self)
        self.command = command
        self.path = path
        self.output = ""
        self.game_process = None
        self.return_code = None
        self.pid = 99999
        self.cedega = False
        self.emergency_kill = False
        logging.debug("Thread initialized")

    def run(self):
        self.timer_id = gobject.timeout_add(2000, self.poke_process)
        if "cedega" in self.command:
            self.cedega = True
        logging.debug(self.command)
        self.game_process = subprocess.Popen(self.command, shell=True,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             cwd=self.path)
        self.output =  self.game_process.stdout

    def poke_process(self):
        if not self.game_process:
            logging.debug("game not running")
            return True
        if self.cedega:
            command = "ps -ef | grep winex_ver | grep -v grep | awk '{print $2}'"
            pid = subprocess.Popenc(command, shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE).communicate()
            self.pid = []
            for item in pid[0].split("\n"):
                if item:
                    self.pid.append(item)
        else:
            self.pid = self.game_process.pid
        self.return_code = self.game_process.poll()
        if self.return_code is not None and not self.cedega:
            logging.debug("Game quit")
            if self.output:
                for stdout in self.output.read().split("\n"):
                    logging.debug(stdout)
            self.pid = None
            return False
        return True
    
class ThreadProcessReader(threading.Thread):
    def __init__(self, stdout):
        threading.Thread.__init__(self)

        self.stdout = stdout
        self.status = "running"
        self.seconds_left = 0

    def run(self):
        seconds_max = 0
        process_ended = False
        while self.status == "running":
            line = self.stdout.read(80)

