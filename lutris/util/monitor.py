"""Process monitor management"""
import os
import shlex
import ctypes
from ctypes.util import find_library
from collections import defaultdict

from lutris.util import system
from lutris.util.log import logger

PR_SET_CHILD_SUBREAPER = 36

# List of process names that are ignored by the process monitoring
EXCLUDED_PROCESSES = [
    "lutris",
    "python",
    "python3",
    "bash",
    "sh",
    "tee",
    "tr",
    "zenity",
    "xkbcomp",
    "xboxdrv",
    "steam",
    "Steam.exe",
    "steamer",
    "steamerrorrepor",
    "gameoverlayui",
    "SteamService.ex",
    "steamwebhelper",
    "steamwebhelper.",
    "PnkBstrA.exe",
    "control",
    "wineserver",
    "services.exe",
    "winedevice.exe",
    "plugplay.exe",
    "explorer.exe",
    "winecfg.exe",
    "wdfmgr.exe",
    "wineconsole",
    "winedbg",
]


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


class ProcessMonitor:
    """Class to keep track of a process and its children status"""

    def __init__(self, include_processes, exclude_processes, exclusion_process):
        """Creates a process monitor

        All arguments accept process names like the ones in EXCLUDED_PROCESSES

        Args:
            exclude_processes (str or list): list of processes that shouldn't be monitored
            include_processes (str or list): list of process that should be forced to be monitored
            exclusion_process (str): If given, ignore all process before this one
        """

        # process names from /proc only contain 15 characters
        self.include_processes = [
            x[0:15] for x in self.parse_process_list(include_processes)
        ]
        self.exclude_processes = [
            x[0:15] for x in EXCLUDED_PROCESSES + self.parse_process_list(exclude_processes)
        ]
        self.exclusion_process = exclusion_process
        self.old_pids = system.get_all_pids()
        # Keep a copy of the monitored processes to allow comparisons
        self.monitored_processes = defaultdict(list)
        self.monitoring_started = False
        self.children = []

    @staticmethod
    def parse_process_list(process_list):
        """Parse a process list that may be given as a string"""
        if not process_list:
            return []
        if isinstance(process_list, str):
            return shlex.split(process_list)
        return process_list

    def iter_children(self, process, topdown=True):
        """Iterator that yields all the children of a process"""
        for child in process.children:
            if topdown:
                yield child
            yield from self.iter_children(child, topdown=topdown)
            if not topdown:
                yield child

    def get_process_status(self, process):
        """Return status of a process"""
        self.children = []
        num_watched_children = 0
        has_passed_exclusion_process = False
        processes = defaultdict(list)
        for child in self.iter_children(process):
            if child.state == 'Z':  # should never happen anymore...
                logger.debug("Unexpected zombie process %s", child)
                try:
                    os.wait3(os.WNOHANG)
                except ChildProcessError:
                    pass
                continue

            if self.exclusion_process:
                if child.name == self.exclusion_process:
                    has_passed_exclusion_process = True
                if not has_passed_exclusion_process:
                    continue

            self.children.append(child)

            if child.pid in self.old_pids:
                processes["external"].append(str(child))
                continue

            if (
                    child.name
                    and child.name in self.exclude_processes
                    and child.name not in self.include_processes
            ):
                processes["excluded"].append(str(child))
                continue
            num_watched_children += 1

        for child in self.monitored_processes["monitored"]:
            if child not in processes["monitored"]:
                self.children.append(child)
                num_watched_children += 1

        for key in processes:
            if processes[key] != self.monitored_processes[key]:
                process_pids = {p.split(":")[0] for p in processes[key]}
                monitored_pids = {p.split(":")[0] for p in self.monitored_processes[key]}
                self.monitored_processes[key] = processes[key]
                if process_pids != monitored_pids:
                    logger.debug(
                        "Processes %s: %s", key, ", ".join(processes[key]) or "no process"
                    )

        if num_watched_children > 0 and not self.monitoring_started:
            logger.debug("Start process monitoring")
            self.monitoring_started = True

        if num_watched_children == 0 and self.monitoring_started:
            return False

        return True
