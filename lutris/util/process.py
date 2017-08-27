import os
import psutil
from lutris.util.log import logger


class InvalidPid(Exception):
    pass


class Process(object):
    def __init__(self, pid, parent=None):
        try:
            self.pid = int(pid)
        except ValueError:
            raise InvalidPid("'%s' is not a valid pid" % pid)
        self.process = None
        self.children = []
        self.children_pids = []
        self.parent = None
        try:
            self.process = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            return
        self.get_children()

    def __repr__(self):
        return "Process {}".format(self.pid)

    def __str__(self):
        if self.process and self.process.is_running():
            return "{} ({}:{})".format(self.name, self.pid, self.state)
        return str(self.pid)

    def get_thread_ids(self):
        """Return a list of thread ids opened by process."""
        if self.process and self.process.is_running():
            return [c.id for c in self.process.threads()]
        else:
            return []

    def get_children_pids_of_thread(self, tid):
        """Return pids of child processes opened by thread `tid` of process."""
        children = []
        try:
            p = psutil.Process(tid)
            children = [c.pid for c in p.children()]
        except:
            pass
        return children

    def get_children(self):
        self.children = []
        for tid in self.get_thread_ids():
            for child_pid in self.get_children_pids_of_thread(tid):
                self.children.append(Process(child_pid, parent=self))

    @property
    def name(self):
        """Filename of the executable."""
        if self.process and self.process.is_running():
            return self.process.name()

    @property
    def state(self):
        """One character from the string "RSDZTW" where R is running, S is
        sleeping in an interruptible wait, D is waiting in uninterruptible disk
        sleep, Z is zombie, T is traced or stopped (on a signal), and W is
        paging.
        """
        if self.process and self.process.is_running():
            return self.process.status()
        return psutil.STATUS_ZOMBIE

    @property
    def cmdline(self):
        """Return command line used to run the process `pid`."""
        if self.process and self.process.is_running():
            return self.process.cmdline()

    @property
    def cwd(self):
        if self.process and self.process.is_running():
            cwd_path = self.process.cwd()
            return os.readlink(cwd_path)

    def kill(self):
        try:
            self.process.kill()
        except OSError:
            logger.error("Could not kill process %s", self.pid)
