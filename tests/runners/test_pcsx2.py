import unittest
from unittest.mock import MagicMock, patch

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.pcsx2 import pcsx2


class TestPCSX2Runner(unittest.TestCase):
    def setUp(self):
        self.runner = pcsx2()
        self.runner.get_executable = lambda: "pcsx2"
        self.runner.get_command = lambda: ["pcsx2"]

    @patch("os.path.isfile")
    def test_play_iso_does_not_exist(self, mock_isfile):
        main_file = "/invalid/path/to/iso"
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = MagicMock()
        self.runner.config = mock_config
        with self.assertRaises(MissingGameExecutableError) as cm:
            self.runner.play()
        self.assertEqual(cm.exception.filename, main_file)

    @patch("lutris.util.system.path_exists")
    @patch("os.path.isfile")
    def test_play_fullscreen(self, mock_path_exists, mock_isfile):
        main_file = "/valid/path/to/iso"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = {"fullscreen": True}
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-fullscreen", main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch("lutris.util.system.path_exists")
    @patch("os.path.isfile")
    def test_play_full_boot(self, mock_path_exists, mock_isfile):
        main_file = "/valid/path/to/iso"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = {"full_boot": True}
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-slowboot", main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch("lutris.util.system.path_exists")
    @patch("os.path.isfile")
    def test_play_nogui(self, mock_path_exists, mock_isfile):
        main_file = "/valid/path/to/iso"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = {"nogui": True}
        self.runner.config = mock_config
        expected = {"command": self.runner.get_command() + ["-nogui", main_file]}
        self.assertEqual(self.runner.play(), expected)

    @patch("lutris.util.system.path_exists")
    @patch("os.path.isfile")
    def test_play(self, mock_path_exists, mock_isfile):
        main_file = "/valid/path/to/iso"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"main_file": main_file}
        mock_config.runner_config = {
            "fullscreen": False,
            "nogui": True,
            "full_boot": True,
        }
        self.runner.config = mock_config
        expected = {"command": [self.runner.get_executable(), "-slowboot", "-nogui", main_file]}
        self.assertEqual(self.runner.play(), expected)
