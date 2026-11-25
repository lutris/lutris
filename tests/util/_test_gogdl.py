import os
import signal
import tempfile
import time
from unittest import TestCase
from unittest.mock import patch

from lutris.util import gogdl
from lutris.util.gogdl import GogdlProgress


class TestGogdlOutcome(TestCase):
    def parse(self, *lines):
        progress = GogdlProgress()
        for line in lines:
            progress.parse_line(line)
        return progress

    def test_nothing_to_do(self):
        for line in ("[V2] INFO: All files look good", "[LINUX] INFO: All files look good", "[V1] INFO: Nothing to do"):
            with self.subTest(line=line):
                self.assertTrue(self.parse(line).nothing_to_do)

    def test_redist_nothing_to_do_is_not_the_game(self):
        self.assertFalse(self.parse("[REDIST] INFO: Nothing to do").nothing_to_do)

    def test_broken_files_counted(self):
        progress = self.parse("[V2] INFO: Found 3 broken files, repairing...")
        self.assertEqual(progress.broken_files, 3)
        self.assertFalse(progress.nothing_to_do)

    def test_plain_progress_has_no_outcome(self):
        progress = self.parse("[V2] INFO: Depot version: 2")
        self.assertFalse(progress.nothing_to_do)
        self.assertIsNone(progress.broken_files)


class TestStopGogdl(TestCase):
    """Cancelling an install must stop gogdl, and anything it started, rather than
    leave it downloading into a folder that is being removed."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.worker_pid_path = os.path.join(temp_dir.name, "worker.pid")
        # Stands in for gogdl: it starts a worker of its own, then waits for it
        self.fake_gogdl = os.path.join(temp_dir.name, "bin", "gogdl")
        os.makedirs(os.path.dirname(self.fake_gogdl))
        with open(self.fake_gogdl, "w", encoding="utf-8") as script:
            script.write('#!/bin/sh\nsleep 60 &\necho $! > "%s"\nwait\n' % self.worker_pid_path)
        os.chmod(self.fake_gogdl, 0o755)
        patcher = patch.object(gogdl.settings, "CACHE_DIR", temp_dir.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def worker_is_running(self):
        with open(self.worker_pid_path, encoding="utf-8") as pid_file:
            pid = int(pid_file.read())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        os.kill(pid, signal.SIGKILL)
        return True

    def test_stopping_gogdl_stops_its_workers(self):
        def on_started(stop):
            for _attempt in range(100):
                if os.path.exists(self.worker_pid_path) and os.path.getsize(self.worker_pid_path):
                    break
                time.sleep(0.05)
            stop()

        with (
            patch.object(gogdl, "_get_gogdl_binary", return_value=self.fake_gogdl),
            patch.object(gogdl, "_write_auth_config", return_value="/nonexistent/auth.json"),
            patch.object(gogdl, "_read_back_token"),
        ):
            with self.assertRaises(RuntimeError):
                gogdl.run_gogdl("download", "1207658924", "/nonexistent/games", on_started=on_started)
        time.sleep(0.2)
        self.assertFalse(self.worker_is_running())
