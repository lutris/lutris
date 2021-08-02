"""Class to manipulate a process"""
import os

from lutris.util.log import logger

IGNORED_PROCESSES = (
    "tracker-store",
    "tracker-extract",
    "kworker",
)


class InvalidPid(Exception):

    """Exception raised when an operation on a non-existent PID is called"""


class Process:

    """Python abstraction a Linux process"""

    def __init__(self, pid):
        try:
            self.pid = int(pid)
        except ValueError:
            raise InvalidPid("'%s' is not a valid pid" % pid)

    def __repr__(self):
        return "Process {}".format(self.pid)

    def __str__(self):
        return "{} ({}:{})".format(self.name, self.pid, self.state)

    def _read_content(self, file_path):
        """Return the contents from a file in /proc"""
        try:
            with open(file_path) as proc_file:
                content = proc_file.read()
        except (ProcessLookupError, FileNotFoundError, PermissionError):
            return ""
        return content

    def get_stat(self, parsed=True):
        stat_filename = "/proc/{}/stat".format(self.pid)
        try:
            with open(stat_filename) as stat_file:
                _stat = stat_file.readline()
        except (ProcessLookupError, FileNotFoundError):
            return None
        if parsed:
            return _stat[_stat.rfind(")") + 1:].split()
        return _stat

    def get_thread_ids(self):
        """Return a list of thread ids opened by process."""
        basedir = "/proc/{}/task/".format(self.pid)
        if os.path.isdir(basedir):
            try:
                return os.listdir(basedir)
            except FileNotFoundError:
                return []
        else:
            return []

    def get_children_pids_of_thread(self, tid):
        """Return pids of child processes opened by thread `tid` of process."""
        children_path = "/proc/{}/task/{}/children".format(self.pid, tid)
        try:
            with open(children_path) as children_file:
                children_content = children_file.read()
        except (FileNotFoundError, ProcessLookupError):
            children_content = ""
        return children_content.strip().split()

    @property
    def name(self):
        """Filename of the executable."""
        _stat = self.get_stat(parsed=False)
        if _stat:
            return _stat[_stat.find("(") + 1:_stat.rfind(")")]
        return None

    @property
    def state(self):
        """One character from the string "RSDZTW" where R is running, S is
        sleeping in an interruptible wait, D is waiting in uninterruptible disk
        sleep, Z is zombie, T is traced or stopped (on a signal), and W is
        paging.
        """
        _stat = self.get_stat()
        if _stat:
            return _stat[0]
        return None

    @property
    def cmdline(self):
        """Return command line used to run the process `pid`."""
        cmdline_path = "/proc/{}/cmdline".format(self.pid)
        _cmdline_content = self._read_content(cmdline_path)
        if _cmdline_content:
            return _cmdline_content.replace("\x00", " ").replace("\\", "/")

    @property
    def cwd(self):
        """Return current working dir of process"""
        cwd_path = "/proc/%d/cwd" % int(self.pid)
        return os.readlink(cwd_path)

    @property
    def environ(self):
        """Return the process' environment variables"""
        environ_path = "/proc/{}/environ".format(self.pid)
        _environ_text = self._read_content(environ_path)
        if not _environ_text:
            return {}
        try:
            return dict([line.split("=", 1) for line in _environ_text.split("\x00") if line])
        except ValueError:
            logger.error("Failed to parse environment variables: %s", _environ_text)
            return {}

    @property
    def children(self):
        """Return the child processes of this process"""
        _children = []
        for tid in self.get_thread_ids():
            for child_pid in self.get_children_pids_of_thread(tid):
                _children.append(Process(child_pid))
        return _children

    def iter_children(self):
        """Iterator that yields all the children of a process"""
        for child in self.children:
            yield child
            yield from child.iter_children()

    def wait_for_finish(self):
        """Waits until the process finishes
        This only works if self.pid is a child process of Lutris
        """
        try:
            pid, ret_status = os.waitpid(int(self.pid) * -1, 0)
        except OSError as ex:
            logger.error("Failed to get exit status for PID %s", self.pid)
            logger.error(ex)
            return -1
        logger.info("PID %s exited with code %s", pid, ret_status)
        return ret_status
