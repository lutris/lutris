from unittest import TestCase

from lutris.installer.commands import CommandsMixin


def report_extraction_progress(progress_callback=None):
    progress_callback(25)
    progress_callback(75)
    return "finished"


class TestExtractionIPC(TestCase):
    def test_progress_reaches_the_parent_process(self):
        commands = CommandsMixin()
        progress = []
        result = commands._killable_process(report_extraction_progress, progress_callback=progress.append)
        self.assertEqual(result, "finished")
        self.assertEqual(progress, [25, 75])
        self.assertIsNone(commands.abort_current_task)
