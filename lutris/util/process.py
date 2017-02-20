import os
import signal
from lutris.util.log import logger


class InvalidPid(Exception):
    pass


class Process(object):
    def __init__(self, pid, parent=None):
        try:
            self.pid = int(pid)
        except ValueError:
            raise InvalidPid("'%s' is not a valid pid" % pid)
        self.children = []
        self.parent = None
        self.get_children()

    def __repr__(self):
        return "Process {}".format(self.pid)

    def get_stat(self, parsed=True):
        stat_filename = "/proc/{}/stat".format(self.pid)
        if not os.path.exists(stat_filename):
            return
        with open(stat_filename) as stat_file:
            try:
                _stat = stat_file.readline()
            except (ProcessLookupError, FileNotFoundError):
                logger.warning('Unable to read stat for process %s', self.pid)
                return
        if parsed:
            return _stat[_stat.rfind(")") + 1:].split()
        return _stat

    def get_thread_ids(self):
        """Return a list of thread ids opened by process."""
        basedir = '/proc/{}/task/'.format(self.pid)
        if os.path.isdir(basedir):
            try:
                return [tid for tid in os.listdir(basedir)]
            except FileNotFoundError:
                return []
        else:
            return []

    def get_children_pids_of_thread(self, tid):
        """Return pids of child processes opened by thread `tid` of process."""
        children = []
        children_path = '/proc/{}/task/{}/children'.format(self.pid, tid)
        if os.path.exists(children_path):
            with open(children_path) as children_file:
                children = children_file.read().strip().split()
        return children

    def get_children(self):
        self.children = []
        for tid in self.get_thread_ids():
            for child_pid in self.get_children_pids_of_thread(tid):
                self.children.append(Process(child_pid, parent=self))

    @property
    def name(self):
        """Filename of the executable."""
        _stat = self.get_stat(parsed=False)
        if _stat:
            return _stat[_stat.find("(") + 1:_stat.rfind(")")]

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

    @property
    def ppid(self):
        """PID of the parent."""
        _stat = self.get_stat()
        if _stat:
            return _stat[1]

    @property
    def pgrp(self):
        """Process group ID of the process."""
        _stat = self.get_stat()
        if _stat:
            return _stat[2]

    @property
    def cmdline(self):
        """Return command line used to run the process `pid`."""
        cmdline_path = '/proc/{}/cmdline'.format(self.pid)
        with open(cmdline_path) as cmdline_file:
            _cmdline = cmdline_file.read().replace('\x00', ' ')
        return _cmdline

    @property
    def cwd(self):
        cwd_path = '/proc/%d/cwd' % int(self.pid)
        return os.readlink(cwd_path)

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except OSError:
            logger.error("Could not kill process %s", self.pid)
