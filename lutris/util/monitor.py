"""Process monitor management"""
import os
import shlex

from lutris.util.process import Process


# List of process names that are ignored by the process monitoring
EXCLUDED_PROCESSES = [
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

    @staticmethod
    def parse_process_list(process_list):
        """Parse a process list that may be given as a string"""
        if not process_list:
            return []
        if isinstance(process_list, str):
            return shlex.split(process_list)
        return process_list

    def iterate_monitored_processes(self):
        for child in Process(os.getpid()).iter_children():
            if child.state == 'Z':
                continue

            if (
                    child.name
                    and child.name in self.exclude_processes
                    and child.name not in self.include_processes
            ):
                pass
            else:
                yield child

    def iterate_all_processes(self):
        return Process(os.getpid()).iter_children()

    def is_game_alive(self):
        "Returns whether at least one nonexcluded process exists"
        for child in self.iterate_monitored_processes():
            return True
        return False
