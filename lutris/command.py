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
from lutris.util import system


#
# This setup uses SIGCHLD as a trigger to check on the runner process
# in order to detect the monitoredcommand's complete exit asynchronously.
#
_pids_to_handlers = {}

def _sigchld_handler(signum, frame):
    try:
        pid, returncode, _ = os.wait3(os.WNOHANG)
    except ChildProcessError:  # already handled by someone else
        return
    try:
        handler = _pids_to_handlers.pop(pid)
    except KeyError:
        return
    GLib.timeout_add(0, handler, returncode)

def _register_handler(pid, handler):
    _pids_to_handlers[pid] = handler

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

        # Is it bad if a path contains a space?
        if any(' ' in path for path in sys.path):
            logging.warning(
                "FIXME not sure how PYTHONPATH operates when paths have "
                "spaces.."
            )
        self.env['PYTHONPATH'] = ':'.join(sys.path)

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
        self.set_log_buffer(log_buffer)
        self.stdout_monitor = None
        self.watch_children_running = False
        self.include_processes = include_processes
        self.exclude_processes = exclude_processes

        # Keep a copy of previously running processes
        self.cwd = self.get_cwd(cwd)

    @property
    def wrapper_command(self):
        return [
            sys.executable, '-m', 'lutris.child_wrapper',
            str(len(self.include_processes)),
            str(len(self.exclude_processes)),
        ] + self.include_processes + self.exclude_processes + self.command

    def set_log_buffer(self, log_buffer):
        """Attach a TextBuffer to this command enables the buffer handler"""
        self.log_buffer = log_buffer
        if self.log_handler_buffer not in self.log_handlers:
            self.log_handlers.append(self.log_handler_buffer)

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
        logger.debug("Running command: %s", " ".join(self.wrapper_command))
        for key, value in self.env.items():
            logger.debug("ENV: %s=\"%s\"", key, value)

        if self.terminal:
            self.game_process = self.run_in_terminal()
        else:
            env = self.apply_environment()
            self.game_process = self.execute_process(self.wrapper_command, env)

        if not self.game_process:
            logger.warning("No game process available")
            return

        _register_handler(self.game_process.pid, self._on_stop)

        if self.watch:
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

    def _on_stop(self, returncode):
        self.is_running = False

        resume_stop = self.stop()
        if not resume_stop:
            logger.info("Full shutdown prevented")
            return False

        self.return_code = returncode
        return False

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
        command = " ".join(['"%s"' % token for token in self.wrapper_command])
        with open(script_path, "w") as script_file:
            script_file.write(dedent(
                """#!/bin/sh
                cd "%s"
                %s
                exec %s
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
        """Stops the current game process and cleans up the instance"""
        try:
            _pids_to_handlers.pop(self.game_process.pid)
        except KeyError:  # may have never been added.
            pass

        try:
            self.game_process.terminate()
        except ProcessLookupError:  # process already dead.
            logger.debug("Management process looks dead already.")

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


def exec_command(command):
    """Execute arbitrary command in a MonitoredCommand

    Used by the --exec command line flag.
    """
    command = MonitoredCommand(shlex.split(command), env=runtime.get_env())
    command.start()
    return command
