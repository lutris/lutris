import subprocess
import time
from unittest import TestCase

from lutris.monitored_command import MonitoredCommand
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestGameProcessHasExited(TestCase):
    def start_process(self, *args):
        command = MonitoredCommand(["true"])
        command.game_process = subprocess.Popen(list(args))
        return command

    def test_running_process_has_not_exited(self):
        command = self.start_process("sleep", "30")
        try:
            self.assertFalse(command.game_process_has_exited)
        finally:
            command.game_process.kill()
            command.game_process.wait()

    def test_exited_process_is_left_to_be_reaped(self):
        command = self.start_process("sh", "-c", "exit 3")
        deadline = time.monotonic() + 10
        while not command.game_process_has_exited:
            self.assertLess(time.monotonic(), deadline, "the process was never reported as exited")
            time.sleep(0.01)
        # game_process_has_exited must not reap the process, or on_stop() could no longer collect its exit status
        self.assertEqual(command.game_process.wait(), 3)

    def test_command_that_never_started_has_exited(self):
        self.assertTrue(MonitoredCommand(["true"]).game_process_has_exited)
