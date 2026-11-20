"""Tests for "Kill all Wine processes"."""

import signal
import unittest
from unittest.mock import patch

from lutris.util.wine import wine

PROTON_LIB = "/home/user/.local/share/Steam/compatibilitytools.d/GE-Proton/files/lib/wine"
EXECUTABLES = {
    101: PROTON_LIB + "/i386-unix/wine-preloader",  # a Windows game
    102: PROTON_LIB + "/x86_64-unix/wine64-preloader",  # one of Wine's own services
    103: "/opt/wine/bin/wineserver (deleted)",  # replaced on disk while running
    104: "/usr/share/codium/codium",  # an editor with --processId in its command line
    105: "/usr/bin/sleep",  # anything else that merely mentions wine
}


def readlink(path):
    pid = int(path.split("/")[2])
    if pid not in EXECUTABLES:
        raise PermissionError(path)  # another user's process
    return EXECUTABLES[pid]


class TestKillAllWineProcesses(unittest.TestCase):
    def test_kills_only_processes_running_wine(self):
        with (
            patch.object(wine.system, "get_running_pid_list", return_value=[*EXECUTABLES, 106]),
            patch.object(wine.os, "readlink", side_effect=readlink),
            patch.object(wine.os, "kill") as kill,
        ):
            self.assertEqual(wine.kill_all_wine_processes(), 3)
        self.assertEqual(
            [call.args for call in kill.call_args_list], [(pid, signal.SIGKILL) for pid in (101, 102, 103)]
        )
