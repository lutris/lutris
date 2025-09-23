import unittest
from unittest.mock import MagicMock, patch

from lutris.runners.vita3k import MissingVitaTitleIDError, vita3k


class TestVita3kRunner(unittest.TestCase):
    def setUp(self):
        self.runner = vita3k()
        self.runner.get_executable = lambda: "vita3k"
        self.runner.get_command = lambda: ["vita3k"]

    @patch("os.path.isfile")
    def test_empty_title_id(self, mock_isfile):
        main_file = ""
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = MagicMock()
        self.runner.config = mock_config
        with self.assertRaises(MissingVitaTitleIDError):
            self.runner.play()

    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_play_fullscreen(self, mock_path_exists, mock_isfile):
        main_file = "PCSG00042"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = {"fullscreen": True}
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-F", "-r", main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_play(self, mock_path_exists, mock_isfile):
        title_id = "PCSG00009"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"title_id": title_id}
        mock_config.runner_config = {"fullscreen": False}
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-r", title_id]}
        self.assertEqual(self.runner.play(), expected)

    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_legacy_main_file_play(self, mock_path_exists, mock_isfile):
        main_file = "PCSG00009"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = {"fullscreen": False}
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-r", main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_play_with_legacy_main_file(self, mock_path_exists, mock_isfile):
        main_file = "PCSG00009"
        title_id = "PCSG00027"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"title_id": title_id, "main_file": main_file}
        mock_config.runner_config = {"fullscreen": False}
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-r", title_id]}
        self.assertEqual(self.runner.play(), expected)
