import unittest
from unittest.mock import MagicMock, patch

from lutris.runners.pcsx2 import pcsx2


class TestPCSX2Runner(unittest.TestCase):

    def setUp(self):
        self.runner = pcsx2()

    @patch('lutris.util.system.path_exists')
    def test_play_iso_does_not_exist(self, mock_path_exists):
        main_file = '/invalid/path/to/iso'
        mock_path_exists.return_value = False
        mock_config = MagicMock()
        mock_config.game_config = {'main_file': main_file}
        mock_config.runner_config = MagicMock()
        self.runner.config = mock_config
        expected = {'error': 'FILE_NOT_FOUND', 'file': main_file}
        self.assertEqual(self.runner.play(), expected)

    @patch('lutris.util.system.path_exists')
    def test_play_fullscreen(self, mock_path_exists):
        main_file = '/valid/path/to/iso'
        mock_path_exists.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {'main_file': main_file}
        mock_config.runner_config = {'fullscreen': True}
        self.runner.config = mock_config
        expected = {'command': [self.runner.get_executable(), '-fullscreen', main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch('lutris.util.system.path_exists')
    def test_play_full_boot(self, mock_path_exists):
        main_file = '/valid/path/to/iso'
        mock_path_exists.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {'main_file': main_file}
        mock_config.runner_config = {'full_boot': True}
        self.runner.config = mock_config
        expected = {'command': [self.runner.get_executable(), '-slowboot', main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch('lutris.util.system.path_exists')
    def test_play_nogui(self, mock_path_exists):
        main_file = '/valid/path/to/iso'
        mock_path_exists.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {'main_file': main_file}
        mock_config.runner_config = {'nogui': True}
        self.runner.config = mock_config
        expected = {'command': [self.runner.get_executable(), '-nogui', main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch('lutris.util.system.path_exists')
    def test_play(self, mock_path_exists):
        main_file = '/valid/path/to/iso'
        mock_path_exists.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {'main_file': main_file}
        mock_config.runner_config = {
            'fullscreen': False, 'nogui': True,
            'full_boot': True,
        }
        self.runner.config = mock_config
        expected = {'command': [self.runner.get_executable(), '-slowboot', '-nogui', main_file]}
        self.assertEqual(self.runner.play(), expected)
