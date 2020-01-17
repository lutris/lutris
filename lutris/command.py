"""Threading module, used to launch games while monitoring them."""

import io
import os
import sys
import fcntl
import shlex
import subprocess
import contextlib
from textwrap import dedent

from gi.repository import GLib

from lutris import settings
from lutris import runtime
from lutris.util.log import logger
from lutris.util import system

WRAPPER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "../share/lutris/bin/lutris-wrapper"))


class MonitoredCommand:
    """Exexcutes a commmand while keeping track of its state"""

    fallback_cwd = "/tmp"

    def __init__(
            self,
            command,
            runner=None,
            env=None,
            term=None,
            cwd=None,
            include_processes=None,
            exclude_processes=None,
            log_buffer=None,
            title=None,
    ):  # pylint: disable=too-many-arguments
        self.ready_state = True
        self.env = self.get_environment(env)

        self.command = command
        self.runner = runner
        self.stop_func = lambda: True
        self.game_process = None
        self.prevent_on_stop = False
        self.return_code = None
        self.terminal = system.find_executable(term)
        self.is_running = True
        self.error = None
        self.log_handlers = [
            self.log_handler_stdout,
            self.log_handler_console_output,
        ]
        self.set_log_buffer(log_buffer)
        self.stdout_monitor = None
        self.include_processes = include_processes or []
        self.exclude_processes = exclude_processes or []

        self.cwd = self.get_cwd(cwd)

        self._stdout = io.StringIO()

        self._title = title if title else command[0]

    @property
    def stdout(self):
        return self._stdout.getvalue()

    @property
    def wrapper_command(self):
        """Return launch arguments for the wrapper script"""

        return [
            WRAPPER_SCRIPT,
            self._title,
            str(len(self.include_processes)),
            str(len(self.exclude_processes)),
        ] + self.include_processes + self.exclude_processes + self.command

    def set_log_buffer(self, log_buffer):
        """Attach a TextBuffer to this command enables the buffer handler"""
        if not log_buffer:
            return
        self.log_buffer = log_buffer
        if self.log_handler_buffer not in self.log_handlers:
            self.log_handlers.append(self.log_handler_buffer)

    def get_cwd(self, cwd):
        """Return the current working dir of the game"""
        if not cwd:
            cwd = self.runner.working_dir if self.runner else None
        return os.path.expanduser(cwd or "~")

    @staticmethod
    def get_environment(user_env):
        """Process the user provided environment variables for use as self.env"""
        env = user_env or {}
        # not clear why this needs to be added, the path is already added in
        # the wrappper script.
        env['PYTHONPATH'] = ':'.join(sys.path)
        # Drop bad values of environment keys, those will confuse the Python
        # interpreter.
        return {
            key: value for key, value in env.items() if "=" not in key
        }

    def get_child_environment(self):
        """Returns the calculated environment for the child process."""
        env = os.environ.copy()
        env.update(self.env)
        return env

    def start(self):
        """Run the thread."""
        logger.debug("Running %s", " ".join(self.wrapper_command))
        for key, value in self.env.items():
            logger.debug("ENV: %s=\"%s\"", key, value)

        if self.terminal:
            self.game_process = self.run_in_terminal()
        else:
            env = self.get_child_environment()
            self.game_process = self.execute_process(self.wrapper_command, env)

        if not self.game_process:
            logger.warning("No game process available")
            return

        GLib.child_watch_add(self.game_process.pid, self.on_stop)

        # make stdout nonblocking.
        fileno = self.game_process.stdout.fileno()
        fcntl.fcntl(
            fileno,
            fcntl.F_SETFL,
            fcntl.fcntl(fileno, fcntl.F_GETFL) | os.O_NONBLOCK
        )

        self.stdout_monitor = GLib.io_add_watch(
            self.game_process.stdout,
            GLib.IO_IN | GLib.IO_HUP,
            self.on_stdout_output,
        )

    def log_handler_stdout(self, line):
        """Add the line to this command's stdout attribute"""
        self._stdout.write(line)

    def log_handler_buffer(self, line):
        """Add the line to the associated LogBuffer object"""
        self.log_buffer.insert(self.log_buffer.get_end_iter(), line, -1)

    def log_handler_console_output(self, line):  # pylint: disable=no-self-use
        """Print the line to stdout"""
        with contextlib.suppress(BlockingIOError):
            sys.stdout.write(line)
            sys.stdout.flush()

    def on_stop(self, _pid, returncode):
        """Callback registered on game process termination"""
        if self.prevent_on_stop:  # stop() already in progress
            return False

        logger.debug("The process has terminated with code %s", returncode)
        self.is_running = False
        self.return_code = returncode

        resume_stop = self.stop()
        if not resume_stop:
            logger.info("Full shutdown prevented")
            return False

        return False

    def on_stdout_output(self, stdout, condition):
        """Called by the stdout monitor to dispatch output to log handlers"""
        if condition == GLib.IO_HUP:
            self.stdout_monitor = None
            return False
        if not self.is_running:
            return False
        try:
            line = stdout.read(262144).decode("utf-8", errors="ignore")
        except ValueError:
            # file_desc might be closed
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
        """Execute and return a subprocess"""
        if self.cwd and not system.path_exists(self.cwd):
            try:
                os.makedirs(self.cwd)
            except OSError:
                logger.error("Failed to create working directory, falling back to %s",
                             self.fallback_cwd)
                self.cwd = "/tmp"
        try:

            return subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=env,
            )
        except OSError as ex:
            logger.exception("Failed to execute %s: %s", " ".join(command), ex)
            self.error = ex.strerror

    def stop(self):
        """Stops the current game process and cleans up the instance"""
        # Prevent stop() being called again by the process exiting
        self.prevent_on_stop = True

        try:
            self.game_process.terminate()
        except ProcessLookupError:  # process already dead.
            logger.debug("Management process looks dead already.")

        if hasattr(self, "stop_func"):
            resume_stop = self.stop_func()
            if not resume_stop:
                return False

        if self.stdout_monitor:
            logger.debug("Detaching logger")
            GLib.source_remove(self.stdout_monitor)
            self.stdout_monitor = None
        else:
            logger.debug("logger already detached")

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
