"""Process monitor management"""
import os
import shlex

from lutris.util.log import logger
from lutris.util.process import Process


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


class ProcessMonitor:
    """Class to keep track of a process and its children status"""

    def __init__(self, include_processes, exclude_processes):
        """Creates a process monitor

        All arguments accept process names like the ones in EXCLUDED_PROCESSES

        Args:
            exclude_processes (str or list): list of processes that shouldn't be monitored
            include_processes (str or list): list of process that should be forced to be monitored
        """

        # process names from /proc only contain 15 characters
        self.include_processes = [
            x[0:15] for x in self.parse_process_list(include_processes)
        ]
        self.exclude_processes = [
            x[0:15] for x in EXCLUDED_PROCESSES + self.parse_process_list(exclude_processes)
        ]
        # Keep a copy of the monitored processes to allow comparisons
        self.children = []
        self.ignored_children = []

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

    @staticmethod
    def _log_changes(label, old, new):
        newpids = {p.pid for p in new}
        oldpids = {p.pid for p in old}
        added = [p for p in new if p.pid not in oldpids]
        removed = [p for p in old if p.pid not in newpids]
        if added:
            logger.debug("New %s processes: %s", label, ', '.join(map(str, added)))
        if removed:
            logger.debug("New %s processes: %s", label, ', '.join(map(str, removed)))

    def refresh_process_status(self):
        """Return status of a process"""
        old_children, self.children = self.children, []
        old_ignored_children, self.ignored_children = self.ignored_children, []

        for child in self.iter_children(Process(os.getpid())):
            if child.state == 'Z':  # should never happen anymore...
                logger.debug("Unexpected zombie process %s", child)
                try:
                    os.wait3(os.WNOHANG)
                except ChildProcessError:
                    pass
                continue

            if (
                    child.name
                    and child.name in self.exclude_processes
                    and child.name not in self.include_processes
            ):
                self.ignored_children.append(child)
            else:
                self.children.append(child)

        self._log_changes('ignored', old_ignored_children, self.ignored_children)
        self._log_changes('monitored', old_children, self.children)

        return len(self.children) > 0
