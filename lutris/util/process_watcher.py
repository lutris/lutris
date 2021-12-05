"""Process management"""
import os
import shlex
import sys

from lutris.util.process import Process

# Processes that are considered sufficiently self-managing by the
# monitoring system. These are not considered game processes for
# the purpose of determining if a game is still running and Lutris
# will never attempt to send signals to these processes.
# This is mostly a minor UX improvement where wine games will exit
# faster if we let the wine processes tear themselves down.
SYSTEM_PROCESSES = {
    "wineserver",
    "services.exe",
    "winedevice.exe",
    "plugplay.exe",
    "explorer.exe",
    "wineconsole",
    "svchost.exe",
    "rpcss.exe",
    "rundll32.exe",
    "mscorsvw.exe",
    "iexplore.exe",
    "start.exe",
    "winedbg.exe",
}


class ProcessWatcher:
    """Keeps track of child processes of the client"""

    def __init__(self, include_processes, exclude_processes):
        """Create a process watcher.
        Params:
            exclude_processes (str or list): list of processes that shouldn't be monitored
            include_processes (str or list): list of process that should be forced to be monitored
        """
        self.unmonitored_processes = (
            self.parse_process_list(exclude_processes) | SYSTEM_PROCESSES
        ) - self.parse_process_list(include_processes)

    @staticmethod
    def parse_process_list(process_list):
        """Parse a process list that may be given as a string"""
        if not process_list:
            return set()
        if isinstance(process_list, str):
            process_list = shlex.split(process_list)
        # process names from /proc only contain 15 characters
        return {p[0:15] for p in process_list}

    @staticmethod
    def iterate_children():
        """Iterates through all children process of the lutris client.
        This is not accurate since not all processes are started by
        lutris but are started by Systemd instead.
        """
        return Process(os.getpid()).iter_children()

    def iterate_processes(self):
        for child in self.iterate_children():
            if child.state == 'Z':
                continue

            if child.name and child.name not in self.unmonitored_processes:
                yield child

    def is_alive(self, message=None):
        """Returns whether at least one watched process exists"""
        if message:
            sys.stdout.write("%s\n" % message)
        return next(self.iterate_processes(), None) is not None
