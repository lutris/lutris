from unittest import TestCase

from lutris.config import LutrisConfig
from lutris.runners.scummvm import scummvm


class TestScummvm(TestCase):
    def test_custom_data_dir(self):
        scummvm_runner = scummvm()
        scummvm_runner.config = LutrisConfig()
        scummvm_runner.config.runner_config["datadir"] = "~/custom/scummvm"

        self.assertEqual(scummvm_runner.get_scummvm_data_dir(), "~/custom/scummvm")
        self.assertEqual(scummvm_runner.get_command()[1], "--extrapath=~/custom/scummvm")
