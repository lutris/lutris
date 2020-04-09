"""Process monitor management"""
import os
import shlex

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
}


class ProcessMonitor:
    """Class to keep track of a process and its children status"""

    def __init__(self, include_processes, exclude_processes):
        """Creates a process monitor

        All arguments accept a list of process names

        Args:
            exclude_processes (str or list): list of processes that shouldn't be monitored
            include_processes (str or list): list of process that should be forced to be monitored
        """
        include_processes = self.parse_process_list(include_processes)
        exclude_processes = self.parse_process_list(exclude_processes)

        self.unmonitored_processes = (exclude_processes | SYSTEM_PROCESSES) - include_processes

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
    def iterate_all_processes():
        return Process(os.getpid()).iter_children()

    def iterate_game_processes(self):
        for child in self.iterate_all_processes():
            if child.state == 'Z':
                continue

            if child.name and child.name not in self.unmonitored_processes:
                yield child

    def iterate_monitored_processes(self):
        for child in self.iterate_all_processes():
            if child.state == 'Z':
                continue

            if child.name not in self.unmonitored_processes:
                yield child

    def is_game_alive(self):
        """Returns whether at least one nonexcluded process exists"""
        return next(self.iterate_game_processes(), None) is not None

    def are_monitored_processes_alive(self):
        return next(self.iterate_monitored_processes(), None) is not None
