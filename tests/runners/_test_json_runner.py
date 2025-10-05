import unittest

from lutris.runners.json import load_json_runners
from lutris.runners.model import _to_platform_dict
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestJsonRunners(unittest.TestCase):
    def test_runner_name_from_json(self):
        """The 'name' key sets runner_name, which puts the executable in the
        runner's own subdirectory of the runners dir."""
        ags = load_json_runners()["ags"]()
        self.assertEqual(ags.runner_name, "ags")
        self.assertEqual(ags.runner_executable_path, "ags/ags.sh")

    def test_platforms_list(self):
        """A list of platforms names each platform after itself."""
        self.assertEqual(
            _to_platform_dict("test.json", ["Commodore 64", "Commodore 128"]),
            {"Commodore 64": "Commodore 64", "Commodore 128": "Commodore 128"},
        )

    def test_platforms_dict(self):
        """A dict of platforms maps each Lutris platform name onto the runner's own code for it."""
        self.assertEqual(
            _to_platform_dict("test.json", {"Commodore 64": "c64", "Commodore 128": "c128"}),
            {"Commodore 64": "c64", "Commodore 128": "c128"},
        )

    def test_platforms_invalid(self):
        """Anything but a list or a dict of platforms is rejected."""
        with self.assertRaises(ValueError):
            _to_platform_dict("test.json", "Commodore 64")
