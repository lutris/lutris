from unittest import TestCase

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
