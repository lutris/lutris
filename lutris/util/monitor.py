"""Process monitor management"""
import ctypes
from ctypes.util import find_library

from lutris.util.log import logger

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
        logger.warning("PR_SET_CHILD_SUBREAPER failed, process watching may fail")
