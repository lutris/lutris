import unittest

from lutris.runners.json import load_json_runners
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestJsonRunners(unittest.TestCase):
    def test_runner_name_from_json(self):
        """The 'name' key sets runner_name, which puts the executable in the
        runner's own subdirectory of the runners dir."""
        ags = load_json_runners()["ags"]()
        self.assertEqual(ags.runner_name, "ags")
        self.assertEqual(ags.runner_executable_path, "ags/ags.sh")
