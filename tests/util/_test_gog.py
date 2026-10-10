import os
import tempfile
from unittest import TestCase

from lutris.util import gog


class TestGetGogGamePath(TestCase):
    def test_returns_none_when_gog_games_folder_is_missing(self):
        with tempfile.TemporaryDirectory() as target_path:
            self.assertIsNone(gog.get_gog_game_path(target_path))

    def test_returns_none_when_gog_games_folder_is_empty(self):
        with tempfile.TemporaryDirectory() as target_path:
            os.makedirs(os.path.join(target_path, "drive_c", "GOG Games"))

            self.assertIsNone(gog.get_gog_game_path(target_path))

    def test_returns_the_installed_game_path(self):
        with tempfile.TemporaryDirectory() as target_path:
            game_path = os.path.join(target_path, "drive_c", "GOG Games", "Some Game")
            os.makedirs(game_path)

            self.assertEqual(gog.get_gog_game_path(target_path), game_path)
