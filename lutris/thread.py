# -*- coding: utf-8 -*-
"""Threading module, used to launch games while monitoring them."""

import os
import sys
import time
import shlex
import threading
import subprocess
import contextlib
from collections import defaultdict
from itertools import chain

from gi.repository import GLib
from textwrap import dedent

from lutris import settings
from lutris import runtime
from lutris.util.log import logger
from lutris.util.process import Process
from lutris.util import system

HEARTBEAT_DELAY = 2000  # Number of milliseconds between each heartbeat
WARMUP_TIME = 5 * 60
MAX_CYCLES_WITHOUT_CHILDREN = 20
# List of process names that are ignored by the process monitoring
EXCLUDED_PROCESSES = [
    'lutris', 'python', 'python3',
    'bash', 'sh', 'tee', 'tr', 'zenity', 'xkbcomp', 'xboxdrv',
    'steam', 'Steam.exe', 'steamer', 'steamerrorrepor', 'gameoverlayui',
    'SteamService.ex', 'steamwebhelper', 'steamwebhelper.', 'PnkBstrA.exe',
    'control', 'wineserver', 'winecfg.exe', 'wdfmgr.exe', 'wineconsole', 'winedbg',
]


class LutrisThread(threading.Thread):
    """Run the game in a separate thread."""
    debug_output = True

    def __init__(self, command, runner=None, env={}, rootpid=None, term=None,
                 watch=True, cwd=None, include_processes=[], exclude_processes=[], log_buffer=None):
        """Thread init"""
        threading.Thread.__init__(self)
        self.ready_state = True
        self.env = env
        self.original_env = {}
        self.command = command
        self.runner = runner
        self.game_process = None
        self.return_code = None
        self.rootpid = rootpid or os.getpid()
        self.terminal = term
        self.watch = watch
        self.is_running = True
        self.stdout = ''
        self.attached_threads = []
        self.cycles_without_children = 0
        self.startup_time = time.time()
        self.monitoring_started = False
        self.daemon = True
        self.error = None
        if isinstance(include_processes, str):
            include_processes = shlex.split(include_processes)
        if isinstance(exclude_processes, str):
            exclude_processes = shlex.split(exclude_processes)
        # process names from /proc only contain 15 characters
        self.include_processes = [x[0:15] for x in include_processes]
        self.exclude_processes = [x[0:15] for x in (EXCLUDED_PROCESSES + exclude_processes)]
        self.log_buffer = log_buffer
        self.stdout_monitor = None

        # Keep a copy of the monitored processes to allow comparisons
        self.monitored_processes = defaultdict(list)

        # Keep a copy of previously running processes
        self.old_pids = system.get_all_pids()

        self.cwd = self.set_cwd(cwd)
        self.env_string = ''
        for (k, v) in self.env.items():
            self.env_string += '%s="%s" ' % (k, v)

        self.command_string = ' '.join(
            ['"%s"' % token for token in self.command]
        )

    def set_cwd(self, cwd):
        if not cwd:
            cwd = self.runner.working_dir if self.runner else '/tmp'
        return os.path.expanduser(cwd)

    def attach_thread(self, thread):
        """Attach child process that need to be killed on game exit."""
        self.attached_threads.append(thread)

    def apply_environment(self):
        """Applies the environment variables to the system's environment."""
        # Store provided environment variables so they can be used by future
        # processes.
        for key, value in self.env.items():
            logger.debug('Storing environment variable %s to %s', key, value)
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Reset library paths if they were not provided
        if not any([key in self.env for key in ('LD_LIBRARY_PATH', 'LD_PRELOAD')]):
            system.reset_library_preloads()

        # Copy the resulting environment to what will be passed to the process
        env = os.environ.copy()
        env.update(self.env)
        return env

    def run(self):
        """Run the thread."""
        logger.debug("Command env: " + self.env_string)
        logger.debug("Running command: " + self.command_string)

        if self.terminal and system.find_executable(self.terminal):
            self.game_process = self.run_in_terminal()
        else:
            self.terminal = False
            env = self.apply_environment()
            self.game_process = self.execute_process(self.command, env)

        if not self.game_process:
            logger.warning("No game process available")
            return

        if self.watch:
            GLib.timeout_add(HEARTBEAT_DELAY, self.watch_children)
            self.stdout_monitor = GLib.io_add_watch(self.game_process.stdout,
                                                    GLib.IO_IN | GLib.IO_HUP,
                                                    self.on_stdout_output)

    def on_stdout_output(self, fd, condition):
        if condition == GLib.IO_HUP:
            self.stdout_monitor = None
            return False
        if not self.is_running:
            return False
        try:
            line = fd.readline().decode('utf-8', errors='ignore')
        except ValueError:
            # fd might be closed
            line = None
        if line:
            self.stdout += line
            if self.log_buffer:
                self.log_buffer.insert(self.log_buffer.get_end_iter(), line, -1)
            if self.debug_output:
                with contextlib.suppress(BlockingIOError):
                    sys.stdout.write(line)
                    sys.stdout.flush()
        return True

    def run_in_terminal(self):
        """Write command in a script file and run it.

        Running it from a file is likely the only way to set env vars only
        for the command (not for the terminal app).
        It's also the only reliable way to keep the term open when the
        game is quit.
        """
        file_path = os.path.join(settings.CACHE_DIR, 'run_in_term.sh')
        with open(file_path, 'w') as f:
            f.write(dedent(
                """\
                #!/bin/sh
                cd "%s"
                %s %s
                exec sh # Keep term open
                """ % (self.cwd, self.env_string, self.command_string)
            ))
            os.chmod(file_path, 0o744)

        return self.execute_process([self.terminal, '-e', file_path])

    def execute_process(self, command, env=None):
        try:
            if self.cwd and not system.path_exists(self.cwd):
                os.makedirs(self.cwd)

            if self.watch:
                pipe=subprocess.PIPE
            else:
                pipe=None

            return subprocess.Popen(command, bufsize=1,
                                    stdout=pipe, stderr=subprocess.STDOUT,
                                    cwd=self.cwd, env=env)
        except OSError as ex:
            logger.exception("Failed to execute %s: %s", ' '.join(command), ex)
            self.error = ex.strerror

    def iter_children(self, process, topdown=True, first=True):
        if self.runner and self.runner.name.startswith('wine') and first:
            if 'WINE' in self.env:
                # Track the correct version of wine for winetricks
                wine_version = self.env['WINE']
            else:
                wine_version = None
            pids = self.runner.get_pids(wine_version)
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

    def restore_environment(self):
        logger.debug("Restoring environment")
        for key in self.original_env:
            if self.original_env[key] is None:
                try:
                    del os.environ[key]
                except KeyError:
                    pass
            else:
                os.environ[key] = self.original_env[key]
        self.original_env = {}

    def stop(self, killall=False):
        for thread in self.attached_threads:
            logger.debug("Stopping thread %s", thread)
            thread.stop()

        if hasattr(self, 'stop_func'):
            resume_stop = self.stop_func()
            if not resume_stop:
                return False

        self.restore_environment()
        self.is_running = False
        self.ready_state = False

        if killall:
            self.killall()
        return True

    def killall(self):
        """Kill every remaining child process"""
        logger.debug("Killing all remaining processes")
        killed_processes = []
        for process in self.iter_children(Process(self.rootpid),
                                          topdown=False):
            killed_processes.append(str(process))
            process.kill()
        if killed_processes:
            logger.debug("Killed processes: %s", ', '.join(killed_processes))

    def is_zombie(self):
        return all([
            p.endswith('Z')
            for p in chain(*[
                self.monitored_processes[key]
                for key in self.monitored_processes
                if key != 'external'
            ])
        ])

    def get_processes(self):
        process = Process(self.rootpid)
        num_children = 0
        num_watched_children = 0
        terminated_children = 0
        passed_terminal_procs = False
        processes = defaultdict(list)
        for child in self.iter_children(process):
            # Exclude terminal processes
            if self.terminal:
                if child.name == "run_in_term.sh":
                    passed_terminal_procs = True
                if not passed_terminal_procs:
                    continue

            num_children += 1
            if child.pid in self.old_pids:
                processes['external'].append(str(child))
                continue

            if (child.name and child.name in self.exclude_processes and
               child.name not in self.include_processes):
                processes['excluded'].append(str(child))
                continue
            num_watched_children += 1
            processes['monitored'].append(str(child))
            if child.state == 'Z':
                terminated_children += 1
        for child in self.monitored_processes['monitored']:
            if child not in processes['monitored']:
                num_children += 1
                num_watched_children += 1
        return processes, num_children, num_watched_children, terminated_children

    def watch_children(self):
        """Poke at the running process(es)."""
        if not self.game_process or not self.is_running:
            logger.error('No game process available')
            return False

        if not self.ready_state:
            # Don't monitor processes until the thread is in a ready state
            self.cycles_without_children = 0
            return True

        processes, num_children, num_watched_children, terminated_children = self.get_processes()
        if num_watched_children > 0 and not self.monitoring_started:
            logger.debug("Start process monitoring")
            self.monitoring_started = True

        for key in processes:
            if processes[key] != self.monitored_processes[key]:
                self.monitored_processes[key] = processes[key]
                logger.debug("Processes {}: {}".format(key, ', '.join(processes[key]) or 'none'))

        if self.runner and hasattr(self.runner, 'watch_game_process'):
            if not self.runner.watch_game_process():
                self.is_running = False
                return False

        if num_watched_children == 0:
            time_since_start = time.time() - self.startup_time
            if self.monitoring_started or time_since_start > WARMUP_TIME:
                self.cycles_without_children += 1
                cycles_left = MAX_CYCLES_WITHOUT_CHILDREN - self.cycles_without_children
                if cycles_left:
                    if cycles_left < 4:
                        logger.debug("Thread aborting in %d cycle", cycles_left)
                else:
                    logger.warning("Thread aborting now")
        else:
            self.cycles_without_children = 0
        max_cycles_reached = (self.cycles_without_children >=
                              MAX_CYCLES_WITHOUT_CHILDREN)

        if num_children == 0 or max_cycles_reached:
            self.is_running = False

            # Remove logger early to avoid issues with zombie processes
            # (unconfirmed)
            if self.stdout_monitor:
                logger.debug("Detaching logger")
                GLib.source_remove(self.stdout_monitor)

            resume_stop = self.stop()
            if not resume_stop:
                logger.info("Full shutdown prevented")
                return False

            if num_children == 0:
                logger.debug("No children left in thread")
                self.game_process.communicate()
            else:
                logger.debug('%d processes are still active', num_children)
                if self.is_zombie():
                    logger.warning('Zombie process detected, killing game process')
                    self.game_process.kill()
            self.return_code = self.game_process.returncode
            return False

        if terminated_children and terminated_children == num_watched_children:
            logger.debug("Waiting for processes to exit")
            try:
                self.game_process.wait(2)
            except subprocess.TimeoutExpired:
                logger.warning("Processes are still running")
                return True
            if self.stdout_monitor:
                logger.debug("Removing stdout monitor")
                GLib.source_remove(self.stdout_monitor)
            logger.debug("Thread is no longer running")
            self.is_running = False
            self.restore_environment()
            return False
        return True


def exec_in_thread(command):
    arguments = shlex.split(command)
    env = runtime.get_env()
    thread = LutrisThread(arguments, env=env)
    thread.start()
    return thread
