import os
from unittest import TestCase
from unittest.mock import patch

from lutris.util.ubisoft import helpers


def _normalized(path):
    return os.path.normcase(os.path.normpath(path))


class TestReturnLocalGamePath(TestCase):
    def test_returns_none_when_the_registry_has_no_install_dir(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.return_value = None

            self.assertIsNone(helpers._return_local_game_path("1234"))

    def test_normalizes_the_registry_path(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.return_value = "C:/Games/Some Game"

            self.assertEqual(helpers._return_local_game_path("1234"), _normalized("C:/Games/Some Game"))


class TestGetLocalGamePath(TestCase):
    def test_returns_none_when_neither_lookup_finds_a_path(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.return_value = None

            self.assertIsNone(helpers.get_local_game_path(None, "1234"))

    def test_falls_back_to_the_special_registry_path(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.side_effect = [None, "D:/Ubisoft Game"]

            game_path = helpers.get_local_game_path("HKEY_LOCAL_MACHINE\\Software\\Ubisoft", "1234")

        self.assertEqual(game_path, "D:/Ubisoft Game")
