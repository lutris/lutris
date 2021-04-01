"""Threading module, used to launch games while monitoring them."""
import contextlib
import fcntl
import uuid
import io
import os
import shlex
import subprocess
import sys

from gi.repository import GLib

from lutris import runtime, settings
from lutris.util import system
from lutris.util.log import logger
from lutris.util.shell import get_terminal_script


def get_wrapper_script_location():
    """Return absolute path of lutris-wrapper script"""
    wrapper_relpath = "share/lutris/bin/lutris-wrapper"
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "..")),
        os.path.dirname(os.path.dirname(settings.__file__)),
        "/usr",
        "/usr/local",
    ]
    for candidate in candidates:
        wrapper_abspath = os.path.join(candidate, wrapper_relpath)
        if os.path.isfile(wrapper_abspath):
            return wrapper_abspath
    raise FileNotFoundError("Couldn't find lutris-wrapper script in any of the expected locations")


WRAPPER_SCRIPT = get_wrapper_script_location()


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
        self.terminal = term
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

    def get_wrapper_command(self):
        """Return launch arguments for the wrapper script"""
        wrapper_command = [
            WRAPPER_SCRIPT,
            self._title,
            str(len(self.include_processes)),
            str(len(self.exclude_processes)),
        ] + self.include_processes + self.exclude_processes
        if not self.terminal:
            return wrapper_command + self.command

        terminal_path = system.find_executable(self.terminal)
        if not terminal_path:
            raise RuntimeError("Couldn't find terminal %s" % self.terminal)
        script_path = get_terminal_script(self.command, self.cwd, self.env)
        return wrapper_command + [terminal_path, "-e", script_path]

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
        env["LUTRIS_GAME_UUID"] = str(uuid.uuid4())
        return {key: value for key, value in env.items() if "=" not in key}

    def get_child_environment(self):
        """Returns the calculated environment for the child process."""
        env = os.environ.copy()
        env.update(self.env)
        return env

    def start(self):
        """Run the thread."""
        # for key, value in self.env.items():
        #     logger.debug("%s=\"%s\"", key, value)
        wrapper_command = self.get_wrapper_command()
        env = self.get_child_environment()
        self.game_process = self.execute_process(wrapper_command, env)

        if not self.game_process:
            logger.error("No game process available")
            return

        GLib.child_watch_add(self.game_process.pid, self.on_stop)

        # make stdout nonblocking.
        fileno = self.game_process.stdout.fileno()
        fcntl.fcntl(fileno, fcntl.F_SETFL, fcntl.fcntl(fileno, fcntl.F_GETFL) | os.O_NONBLOCK)

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

    def get_return_code(self):
        """Get the return code from the file written by the wrapper"""
        return_code_path = "/tmp/lutris-%s" % self.env["LUTRIS_GAME_UUID"]
        if os.path.exists(return_code_path):
            with open(return_code_path) as return_code_file:
                return_code = return_code_file.read()
            os.unlink(return_code_path)
        else:
            logger.warning("No file %s", return_code_path)
        return return_code

    def on_stop(self, pid, _user_data):
        """Callback registered on game process termination"""
        if self.prevent_on_stop:  # stop() already in progress
            return False
        self.game_process.wait()
        self.return_code = self.get_return_code()
        self.is_running = False
        logger.debug("Process %s has terminated with code %s", pid, self.return_code)
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

    def execute_process(self, command, env=None):
        """Execute and return a subprocess"""
        if self.cwd and not system.path_exists(self.cwd):
            try:
                os.makedirs(self.cwd)
            except OSError:
                logger.error("Failed to create working directory, falling back to %s", self.fallback_cwd)
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
        except ProcessLookupError:
            # process already dead.
            pass

        resume_stop = self.stop_func()
        if not resume_stop:
            logger.warning("Stop execution halted by demand of stop_func")
            return False

        if self.stdout_monitor:
            GLib.source_remove(self.stdout_monitor)
            self.stdout_monitor = None

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
