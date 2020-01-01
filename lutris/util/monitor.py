"""Process monitor management"""
import os
import shlex

from lutris.util.process import Process


# List of process names that are not considered game processes. A game
# is not "running" until a process that isn't one of the following
# (or a system process; see below) belongs in its process tree.
# Processes in this list will be sent SIGTERM when the game has exited

# FIXME don't ignore any process, makes launching Steam possible
EXCLUDED_PROCESSES = []
_EXCLUDED_PROCESSES = [
    "lutris",
    "python",
    "python3",
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
    "explorer.exe",
    "winecfg.exe",
    "wdfmgr.exe",
    "wineconsole",
    "winedbg",
]

# Processes that are considered sufficiently self-managing by the
# monitoring system. These are not considered game processes for the
# purpose of determining if a game is still running (just like the
# EXCLUDED_PROCESSES above) and Lutris will never attempt to send
# signals to these processes.
# This is mostly a minor UX improvement where wine games will exit
# faster if we let the wine processes tear themselves down.
SYSTEM_PROCESSES = {
    "wineserver",
    "services.exe",
    "winedevice.exe",
    "plugplay.exe",
}


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
        include_processes = {
            x[0:15] for x in self.parse_process_list(include_processes)
        }
        self.exclude_processes = {
            x[0:15] for x in EXCLUDED_PROCESSES + self.parse_process_list(exclude_processes)
        }
        self.nongame_processes = (self.exclude_processes | SYSTEM_PROCESSES) - include_processes

    @staticmethod
    def parse_process_list(process_list):
        """Parse a process list that may be given as a string"""
        if not process_list:
            return []
        if isinstance(process_list, str):
            return shlex.split(process_list)
        return process_list

    def iterate_game_processes(self):
        for child in self.iterate_all_processes():
            if child.state == 'Z':
                continue

            if child.name and child.name not in self.nongame_processes:
                yield child

    def iterate_monitored_processes(self):
        for child in self.iterate_all_processes():
            if child.state == 'Z':
                continue

            if child.name not in SYSTEM_PROCESSES:
                yield child

    def iterate_all_processes(self):
        return Process(os.getpid()).iter_children()

    def is_game_alive(self):
        "Returns whether at least one nonexcluded process exists"
        for child in self.iterate_game_processes():
            return True
        return False

    def are_monitored_processes_alive(self):
        for child in self.iterate_monitored_processes():
            return True
        return False
