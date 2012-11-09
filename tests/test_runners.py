import logging
from unittest import TestCase

from lutris import runners

LOGGER = logging.getLogger(__name__)


class ImportRunnerTest(TestCase):

    def test_runner_modules(self):

        runner_list = runners.__all__
        self.assertIn("linux", runner_list)
        self.assertIn("wine", runner_list)
        self.assertIn("pcsx", runner_list)
        self.assertIn("uae", runner_list)

    def test_import_module(self):
        for runner_name in runners.__all__:
            runner_class = runners.import_runner(runner_name)
            self.assertEqual(runner_class().__class__.__name__, runner_name)

    def test_options(self):
        for runner_name in runners.__all__:
            LOGGER.info("Importing %s", runner_name)
            runner_class = runners.import_runner(runner_name)
            runner = runner_class()
            self.assertTrue(hasattr(runner, 'game_options'),
                            "%s doesn't have game options" % runner_name)
            for option in runner.game_options:
                self.assertIn('type', option)
                self.assertFalse(option['type'] == 'single')
