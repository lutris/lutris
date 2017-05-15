import logging
from unittest.mock import patch

from lutris.config import LutrisConfig
from lutris import runners
from test_pga import DatabaseTester

LOGGER = logging.getLogger(__name__)


class ImportRunnerTest(DatabaseTester):
    def test_runner_modules(self):
        runner_list = runners.__all__
        self.assertIn("linux", runner_list)
        self.assertIn("wine", runner_list)
        self.assertIn("libretro", runner_list)
        self.assertIn("fsuae", runner_list)

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
            self.assertTrue(hasattr(runner, 'runner_options'))
            for option in runner.game_options:
                self.assertIn('type', option)
                self.assertFalse(option['type'] == 'single')

    def test_get_system_config(self):
        def fake_yaml_reader(path):
            if not path:
                return {}
            if 'system.yml' in path:
                return {'system': {'resolution': '640x480'}}
            return {}

        with patch('lutris.config.read_yaml_from_file') as yaml_reader:
            yaml_reader.side_effect = fake_yaml_reader
            wine_runner = runners.import_runner('wine')
            wine = wine_runner()
            self.assertEqual(wine.system_config.get('resolution'), '640x480')

    def test_runner_config_overrides_system_config(self):
        def fake_yaml_reader(path):
            if not path:
                return {}
            if 'system.yml' in path:
                return {'resolution': '640x480'}
            if 'wine.yml' in path:
                return {'system': {'resolution': '800x600'}}
            return {}

        with patch('lutris.config.read_yaml_from_file') as yaml_reader:
            yaml_reader.side_effect = fake_yaml_reader
            wine_runner = runners.import_runner('wine')
            wine = wine_runner()
            self.assertEqual(wine.system_config.get('resolution'), '800x600')

    def test_game_config_overrides_all(self):
        def fake_yaml_reader(path):
            if not path:
                return {}
            if 'system.yml' in path:
                return {'system': {'resolution': '640x480'}}
            if 'wine.yml' in path:
                return {'system': {'resolution': '800x600'}}
            if 'rage.yml' in path:
                return {'system': {'resolution': '1920x1080'}}
            return {}

        with patch('lutris.config.read_yaml_from_file') as yaml_reader:
            yaml_reader.side_effect = fake_yaml_reader
            wine_runner = runners.import_runner('wine')
            game_config = LutrisConfig(game_config_id='rage',
                                       runner_slug='wine')
            wine = wine_runner(game_config)
            self.assertEqual(wine.system_config.get('resolution'), '1920x1080')

    def test_system_config_with_no_system_yml(self):
        def fake_yaml_reader(path):
            if not path:
                return {}
            if 'system.yml' in path:
                return {}
            if 'wine.yml' in path:
                return {'system': {'resolution': '800x600'}}
            if 'rage.yml' in path:
                return {'system': {'resolution': '1680x1050'},
                        'runner': 'wine'}
            return {}

        with patch('lutris.config.read_yaml_from_file') as yaml_reader:
            yaml_reader.side_effect = fake_yaml_reader
            wine_runner = runners.import_runner('wine')
            game_config = LutrisConfig(runner_slug='wine',
                                       game_config_id='rage')
            self.assertEqual(game_config.game_config_id, 'rage')
            self.assertEqual(game_config.runner_slug, 'wine')
            wine = wine_runner(game_config)
            self.assertEqual(wine.system_config.get('resolution'), '1680x1050')
