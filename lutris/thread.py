# -*- coding: utf-8 -*-
"""Threading module, used to launch games while monitoring them"""

import os
import sys
import threading
import subprocess

from gi.repository import GLib
from textwrap import dedent

from lutris import settings
from lutris.util.log import logger
from lutris.util.process import Process
from lutris.util.system import find_executable

HEARTBEAT_DELAY = 1500  # Number of milliseconds between each heartbeat


class LutrisThread(threading.Thread):
    """Runs the game in a separate thread"""
    debug_output = True

    def __init__(self, command, runner=None, env={}, rootpid=None, term=None):
        """Thread init"""
        threading.Thread.__init__(self)
        self.env = env
        self.command = command
        self.runner = runner
        self.game_process = None
        self.return_code = None
        self.rootpid = rootpid or os.getpid()
        self.terminal = term
        self.is_running = True
        self.stdout = ''
        self.attached_threads = []
        self.cycles_without_children = 0
        self.max_cycles_without_children = 40

        if self.runner:
            self.path = runner.working_dir
        else:
            self.path = '/tmp/'

        self.env_string = ''
        for (k, v) in self.env.iteritems():
            self.env_string += '%s="%s" ' % (k, v)

        self.command_string = ' '.join(
            ['"%s"' % token for token in self.command]
        )

    def attach_thread(self, thread):
        """Attach child process that need to be killed on game exit"""
        self.attached_threads.append(thread)

    def run(self):
        """Run the thread"""
        logger.debug("Command env: " + self.env_string)
        logger.debug("Running command: " + self.command_string)
        GLib.timeout_add(HEARTBEAT_DELAY, self.watch_children)

        if self.terminal and find_executable(self.terminal):
            self.run_in_terminal()
        else:
            self.terminal = False
            env = os.environ.copy()
            env.update(self.env)
            self.game_process = subprocess.Popen(self.command, bufsize=1,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.STDOUT,
                                                 cwd=self.path, env=env)
        os.chdir(os.path.expanduser('~'))

        for line in iter(self.game_process.stdout.readline, ''):
            self.stdout += line
            if self.debug_output:
                sys.stdout.write(line)

    def run_in_terminal(self):

        # Write command in a script file.
        '''Running it from a file is likely the only way to set env vars only
        for the command (not for the terminal app).
        It also permits the only reliable way to keep the term open when the
        game is exited.'''
        file_path = os.path.join(settings.CACHE_DIR, 'run_in_term.sh')
        with open(file_path, 'w') as f:
            f.write(dedent(
                """\
                #!/bin/sh
                cd "%s"
                %s %s
                exec sh # Keep term open
                """ % (self.path, self.env_string, self.command_string)
            ))
            os.chmod(file_path, 0744)

        term_command = [self.terminal, '-e', file_path]
        self.game_process = subprocess.Popen(term_command, bufsize=1,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             cwd=self.path)
        os.chdir(os.path.expanduser('~'))

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
            logger.debug("Stopping thread %s", thread)
            thread.stop()
        if hasattr(self, 'stop_func'):
            logger.debug("Calling custom stop function %s", self.stop_func)
            self.stop_func()
        if not killall:
            return
        for process in self.iter_children(Process(self.rootpid),
                                          topdown=False):
            logger.debug("Killing process %s", process)
            process.kill()

    def watch_children(self):
        """pokes at the running process"""
        process = Process(self.rootpid)
        num_children = 0
        num_watched_children = 0
        terminated_children = 0
        passed_terminal_procs = False
        for child in self.iter_children(process):
            # Exclude terminal processes
            if self.terminal:
                if child.name == "run_in_term.sh":
                    passed_terminal_procs = True
                if not passed_terminal_procs:
                    continue

            num_children += 1
            # Exclude other wrapper processes
            if child.name in ('steamwebhelper', 'steam', 'sh', 'tee', 'bash',
                              'Steam.exe', 'steamwebhelper.',
                              'steamerrorrepor'):
                continue
            num_watched_children += 1
            logger.debug("{}\t{}\t{}".format(child.pid,
                                             child.state,
                                             child.name))
            if child.state == 'Z':
                terminated_children += 1
        if terminated_children and terminated_children == num_watched_children:
            logger.debug("All children terminated")
            self.game_process.wait()
        if num_watched_children == 0:
            self.cycles_without_children += 1
        if(num_children == 0
           or self.cycles_without_children >= self.max_cycles_without_children):
            logger.debug("No children left in thread, exiting")
            self.is_running = False
            self.return_code = self.game_process.returncode
            return False
        return True
