# -*- coding: utf-8 -*-
"""Threading module, used to launch games while monitoring them"""

import os
import sys
import threading
import subprocess

from gi.repository import GLib

from lutris.util.log import logger
from lutris.util.process import Process

HEARTBEAT_DELAY = 1000  # Number of milliseconds between each heartbeat


class LutrisThread(threading.Thread):
    """Runs the game in a separate thread"""
    debug_output = False

    def __init__(self, command, runner=None, env={}, rootpid=None):
        """Thread init"""
        threading.Thread.__init__(self)
        self.env = env
        self.command = command
        self.runner = runner
        self.game_process = None
        self.return_code = None
        self.rootpid = rootpid or os.getpid()
        self.is_running = True
        self.stdout = ''
        self.attached_threads = []
        self.cycles_without_children = 0

        if self.runner:
            self.path = runner.working_dir
        else:
            self.path = '/tmp/'

    def attach_thread(self, thread):
        """Attach child process that need to be killed on game exit"""
        self.attached_threads.append(thread)

    def run(self):
        """Run the thread"""
        logger.debug("Thread running: %s", self.command)
        GLib.timeout_add(HEARTBEAT_DELAY, self.watch_children)
        self.game_process = subprocess.Popen(self.command, bufsize=1,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             cwd=self.path, env=self.env)
        for line in iter(self.game_process.stdout.readline, ''):
            self.stdout += line
            if self.debug_output:
                sys.stdout.write(line)

    def iter_children(self, process, topdown=True, first=True):
        if self.runner and self.runner.name.startswith('wine') and first:
            pids = self.runner.get_pids()
            for pid in pids:
                wineprocess = Process(pid)
                if wineprocess.name not in self.runner.core_processes:
                    process.children.append(wineprocess)
        for child in process.children:
            if topdown:
                yield child
            subs = self.iter_children(child, topdown=topdown, first=False)
            for sub in subs:
                yield sub
            if not topdown:
                yield child

    def set_stop_command(self, func):
        self.stop_func = func

    def stop(self, killall=False):
        for thread in self.attached_threads:
            thread.stop()
        if hasattr(self, 'stop_func'):
            self.stop_func()
            if not killall:
                return
        for process in self.iter_children(Process(self.rootpid), topdown=False):
            process.kill()

    def watch_children(self):
        """pokes at the running process"""
        process = Process(self.rootpid)
        num_children = 0
        num_watched_children = 0
        terminated_children = 0
        for child in self.iter_children(process):
            num_children += 1
            if child.name in ('steamwebhelper', 'steam', 'sh', 'tee', 'bash'):
                continue
            num_watched_children += 1
            print "{}\t{}\t{}".format(child.pid,
                                      child.state,
                                      child.name)
            if child.state == 'Z':
                terminated_children += 1
        if terminated_children and terminated_children == num_watched_children:
            self.game_process.wait()
        if num_watched_children == 0:
            self.cycles_without_children += 1
        if num_children == 0 or self.cycles_without_children >= 3:
            self.is_running = False
            return False
        return True
