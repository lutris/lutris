import unittest

from lutris import runners
from lutris.runners.names import RunnerName


class TestRunnerName(unittest.TestCase):
    def test_names_are_loadable_runners(self):
        for name in RunnerName:
            self.assertTrue(runners.is_valid_runner_name(name.value), name)

    def test_compares_equal_to_plain_strings(self):
        self.assertEqual(RunnerName.WINE, "wine")
        self.assertIn("linux", (RunnerName.LINUX, RunnerName.WINE))
        self.assertEqual(RunnerName("steam"), RunnerName.STEAM)
