"""Class to manipulate a process"""
import os


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
                return [tid for tid in os.listdir(basedir)]
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
        with open(cmdline_path) as cmdline_file:
            _cmdline = cmdline_file.read().replace("\x00", " ")
        return _cmdline

    @property
    def cwd(self):
        """Return current working dir of process"""
        cwd_path = "/proc/%d/cwd" % int(self.pid)
        return os.readlink(cwd_path)

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
