# coding: utf-8
import os
import time
import ctypes
import sys
import subprocess
import signal
from ctypes.util import find_library
from lutris.util.log import logger
from lutris.util.monitor import ProcessMonitor

PR_SET_CHILD_SUBREAPER = 36
def set_child_subreaper():
    """Sets the current process to a subreaper.

    A subreaper fulfills the role of init(1) for its descendant
    processes.  When a process becomes orphaned (i.e., its
    immediate parent terminates) then that process will be
    reparented to the nearest still living ancestor subreaper.
    Subsequently, calls to getppid() in the orphaned process will
    now return the PID of the subreaper process, and when the
    orphan terminates, it is the subreaper process that will
    receive a SIGCHLD signal and will be able to wait(2) on the
    process to discover its termination status.

    The setting of this bit is not inherited by children created
    by fork(2) and clone(2).  The setting is preserved across
    execve(2).

    Establishing a subreaper process is useful in session
    management frameworks where a hierarchical group of processes
    is managed by a subreaper process that needs to be informed
    when one of the processes—for example, a double-forked daemon—
    terminates (perhaps so that it can restart that process).
    Some init(1) frameworks (e.g., systemd(1)) employ a subreaper
    process for similar reasons.
    """
    result = ctypes.CDLL(find_library('c')).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0, 0)
    if result == -1:
        print("PR_SET_CHILD_SUBREAPER failed, process watching may fail")


def main():
    set_child_subreaper()
    _, include_proc_count, exclude_proc_count, *args = sys.argv

    # So I'm too lazy to implement real argument parsing... sorry.
    include_proc_count = int(include_proc_count)
    exclude_proc_count = int(exclude_proc_count)
    include_procs, args = args[:include_proc_count], args[include_proc_count:]
    exclude_procs, args = args[:exclude_proc_count], args[exclude_proc_count:]

    monitor = ProcessMonitor(include_procs, exclude_procs)

    def sig_handler(signum, frame):
        signal.signal(signal.SIGTERM, old_sigterm_handler)
        signal.signal(signal.SIGINT, old_sigint_handler)
        monitor.refresh_process_status()
        for child in monitor.children:
            os.kill(child.pid, signum)

    old_sigterm_handler = signal.signal(signal.SIGTERM, sig_handler)
    old_sigint_handler = signal.signal(signal.SIGINT, sig_handler)

    returncode = subprocess.run(args).returncode
    try:
        while True:
            os.wait3(0)
            if not monitor.refresh_process_status():
                break
    except ChildProcessError:
        pass
    sys.exit(returncode)


if __name__ == "__main__":
    main()
