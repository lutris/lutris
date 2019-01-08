"""Threading module, used to launch games while monitoring them."""

import os
import sys
import shlex
import subprocess
import contextlib
import signal
import weakref
import functools
from textwrap import dedent

from gi.repository import GLib

from lutris import settings
from lutris import runtime
from lutris.util.log import logger
from lutris.util.process import Process
from lutris.util.monitor import ProcessMonitor
from lutris.util import system

HEARTBEAT_DELAY = 2000  # Number of milliseconds between each heartbeat
DEFAULT_MAX_CYCLES = 5


def _reentrancy_guard(func):
    """
    Prevents an argumentless method from having two invocations running
    at the same time. self must be hashable.
    """
    guards = weakref.WeakSet()

    @functools.wraps(func)
    def inner(self):
        if self not in guards:
            guards.add(self)
            try:
                return func(self)
            finally:
                guards.remove(self)

    return inner


#
# This setup uses SIGCHLD as a trigger to check on the runner process
# in order to detect the monitoredcommand's complete exit early instead
# of on the next polling interval. Because processes can be created
# and exited very rapidly, it includes a 16 millisecond debounce.
#
_commands = weakref.WeakSet()
_timeout_set = False


def _trigger_early_poll():
    global _timeout_set
    try:
        # prevent changes to size during iteration
        for command in set(_commands):
            command.watch_children()
    except Exception:
        logger.exception("Signal handler exception")
    finally:
        _timeout_set = False
    return False


def _sigchld_handler(signum, frame):
    global _timeout_set
    try:
        os.wait3(os.WNOHANG)
    except ChildProcessError:  # already handled by someone else
        return
    if _commands and not _timeout_set:
        GLib.timeout_add(16, _trigger_early_poll)
        _timeout_set = True


signal.signal(signal.SIGCHLD, _sigchld_handler)


class MonitoredCommand:
    """Run the game."""

    def __init__(
            self,
            command,
            runner=None,
            env=None,
            term=None,
            watch=True,
            cwd=None,
            include_processes=None,
            exclude_processes=None,
            log_buffer=None,
    ):
        self.ready_state = True
        if env is None:
            self.env = {}
        else:
            self.env = env
        self.original_env = {}
        self.command = command
        self.runner = runner
        self.stop_func = lambda: True
        self.game_process = None
        self.return_code = None
        self.terminal = system.find_executable(term)
        self.watch = watch
        self.is_running = True
        self.stdout = ""
        self.daemon = True
        self.error = None
        self.log_handlers = [
            self.log_handler_stdout,
            self.log_handler_console_output,
        ]
        if log_buffer:
            self.log_handlers.append(self.log_handler_buffer)
        self.stdout_monitor = None
        self.watch_children_running = False

        # Keep a copy of previously running processes
        self.cwd = self.get_cwd(cwd)
        self.process_monitor = ProcessMonitor(
            include_processes,
            exclude_processes,
            "run_in_term.sh" if self.terminal else None
        )

    def get_cwd(self, cwd):
        """Return the current working dir of the game"""
        if not cwd:
            cwd = self.runner.working_dir if self.runner else "/tmp"
        return os.path.expanduser(cwd)

    def apply_environment(self):
        """Applies the environment variables to the system's environment."""
        # Store provided environment variables so they can be used by future
        # processes.
        for key, value in self.env.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = str(value)

        # Reset library paths if they were not provided
        if not any([key in self.env for key in ("LD_LIBRARY_PATH", "LD_PRELOAD")]):
            system.reset_library_preloads()

        # Copy the resulting environment to what will be passed to the process
        env = os.environ.copy()
        env.update(self.env)
        return env

    def start(self):
        """Run the thread."""
        logger.debug("Running command: %s", " ".join(self.command))
        for key, value in self.env.items():
            logger.debug("ENV: %s=\"%s\"", key, value)

        if self.terminal:
            self.game_process = self.run_in_terminal()
        else:
            env = self.apply_environment()
            self.game_process = self.execute_process(self.command, env)

        if not self.game_process:
            logger.warning("No game process available")
            return

        _commands.add(self)
        if self.watch:
            GLib.timeout_add(HEARTBEAT_DELAY, self.watch_children)
            self.stdout_monitor = GLib.io_add_watch(
                self.game_process.stdout,
                GLib.IO_IN | GLib.IO_HUP,
                self.on_stdout_output,
            )

    def log_handler_stdout(self, line):
        """Add the line to this command's stdout attribute"""
        self.stdout += line

    def log_handler_buffer(self, line):
        """Add the line to the associated LogBuffer object"""
        self.log_buffer.insert(self.log_buffer.get_end_iter(), line, -1)

    def log_handler_console_output(self, line):
        """Print the line to stdout"""
        with contextlib.suppress(BlockingIOError):
            sys.stdout.write(line)
            sys.stdout.flush()

    def on_stdout_output(self, fd, condition):
        if condition == GLib.IO_HUP:
            self.stdout_monitor = None
            return False
        if not self.is_running:
            return False
        try:
            line = fd.readline().decode("utf-8", errors="ignore")
        except ValueError:
            # fd might be closed
            return True
        if "winemenubuilder.exe" in line:
            return True
        for log_handler in self.log_handlers:
            log_handler(line)
        return True

    def run_in_terminal(self):
        """Write command in a script file and run it.

        Running it from a file is likely the only way to set env vars only
        for the command (not for the terminal app).
        It's also the only reliable way to keep the term open when the
        game is quit.
        """
        script_path = os.path.join(settings.CACHE_DIR, "run_in_term.sh")
        exported_environment = "\n".join(
            'export %s="%s" ' % (key, value)
            for key, value in self.env.items()
        )
        command = " ".join(['"%s"' % token for token in self.command])
        with open(script_path, "w") as script_file:
            script_file.write(dedent(
                """#!/bin/sh
                cd "%s"
                %s
                %s
                exec sh # Keep term open
                """ % (self.cwd, exported_environment, command)
            ))
            os.chmod(script_path, 0o744)
        return self.execute_process([self.terminal, "-e", script_path])

    def execute_process(self, command, env=None):
        try:
            if self.cwd and not system.path_exists(self.cwd):
                os.makedirs(self.cwd)

            if self.watch:
                pipe = subprocess.PIPE
            else:
                pipe = None

            return subprocess.Popen(
                command,
                bufsize=1,
                stdout=pipe,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=env,
            )
        except OSError as ex:
            logger.exception("Failed to execute %s: %s", " ".join(command), ex)
            self.error = ex.strerror

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

    def stop(self):
        """Stops the current game process and cleans up the thread"""
        try:
            _commands.remove(self)
        except KeyError:  # may have never been added.
            pass

        # Remove logger early to avoid issues with zombie processes
        # (unconfirmed)
        if self.stdout_monitor:
            logger.debug("Detaching logger")
            GLib.source_remove(self.stdout_monitor)

        if hasattr(self, "stop_func"):
            resume_stop = self.stop_func()
            if not resume_stop:
                return False

        self.restore_environment()
        self.is_running = False
        self.ready_state = False

        return True

    def get_root_process(self):
        """Return root process, including Wine processes as children"""
        process = Process(os.getpid())
        if self.runner and self.runner.name.startswith("wine"):
            # Track the correct version of wine for winetricks
            wine_version = self.env.get("WINE") or None
            for pid in self.runner.get_pids(wine_version):
                wineprocess = Process(pid)
                if wineprocess.name not in self.runner.core_processes:
                    process.children.append(wineprocess)
        return process

    @_reentrancy_guard
    def watch_children(self):
        """Poke at the running process(es).

        Return:
            bool: True to keep monitoring, False to stop (Used by GLib.timeout_add)
        """
        if not self.game_process:
            logger.error("No game process available")
            return False
        if not self.is_running:
            logger.error("Game is not running")
            return False
        if not self.ready_state:
            # Don't monitor processes until the thread is in a ready state
            self.process_monitor.cycles_without_children = 0
            return True

        if not self.process_monitor.get_process_status(self.get_root_process()):
            self.is_running = False

            resume_stop = self.stop()
            if not resume_stop:
                logger.info("Full shutdown prevented")
                return False

            if not self.process_monitor.children:
                self.game_process.communicate()
            else:
                logger.debug("%d processes are still active", len(self.process_monitor.children))
            self.return_code = self.game_process.returncode
            return False

        return True


def exec_in_thread(command):
    """Execute arbitrary command in a Lutris thread

    Used by the --exec command line flag.
    """
    command = MonitoredCommand(shlex.split(command), env=runtime.get_env())
    command.start()
    return command
