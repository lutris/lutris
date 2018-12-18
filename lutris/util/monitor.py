"""Process monitor management"""
import os
import shlex
import ctypes
from ctypes.util import find_library
from collections import defaultdict

from lutris.util.process import Process
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


class ProcessMonitor():
    """Class to keep track of a process and its children status"""

    def __init__(self, thread, include_processes, exclude_processes):
        self.process_thread = thread
        self.old_pids = system.get_all_pids()

        if include_processes is None:
            include_processes = []
        elif isinstance(include_processes, str):
            include_processes = shlex.split(include_processes)
        if exclude_processes is None:
            exclude_processes = []
        elif isinstance(exclude_processes, str):
            exclude_processes = shlex.split(exclude_processes)
        # process names from /proc only contain 15 characters
        self.include_processes = [x[0:15] for x in include_processes]
        self.exclude_processes = [
            x[0:15] for x in EXCLUDED_PROCESSES + exclude_processes
        ]

        # Keep a copy of the monitored processes to allow comparisons
        self.monitored_processes = defaultdict(list)

    def iter_children(self, process, topdown=True, first=True):
        """Iterator that yields all the children of a process"""
        if self.process_thread.runner.name.startswith("wine") and first:
            # Track the correct version of wine for winetricks
            wine_version = self.process_thread.env.get("WINE") or None
            pids = self.process_thread.runner.get_pids(wine_version)
            for pid in pids:
                wineprocess = Process(pid)
                if wineprocess.name not in self.process_thread.runner.core_processes:
                    process.children.append(wineprocess)
        for child in process.children:
            if topdown:
                yield child
            subs = self.iter_children(child, topdown=topdown, first=False)
            for sub in subs:
                yield sub
            if not topdown:
                yield child

    def get_processes(self):
        """Return sorted by monitoring state.

        TODO write more docs about the return data structure

        OR

        refactor the shit out of it
        """
        process = Process(self.process_thread.rootpid)
        num_children = 0
        num_watched_children = 0
        passed_terminal_procs = False
        processes = defaultdict(list)
        for child in self.iter_children(process):
            if child.state == 'Z':
                os.wait3(os.WNOHANG)
                continue

            # Exclude terminal processes
            if self.process_thread.terminal:
                if child.name == "run_in_term.sh":
                    passed_terminal_procs = True
                if not passed_terminal_procs:
                    continue

            num_children += 1
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
                num_children += 1
                num_watched_children += 1

        for key in processes:
            if processes[key] != self.monitored_processes[key]:
                self.monitored_processes[key] = processes[key]
                logger.debug(
                    "Processes %s: %s", key, ", ".join(processes[key]) or "none"
                )

        return processes, num_children, num_watched_children
