"""Tests for Steam shortcut generation."""

import unittest
from unittest.mock import patch

from lutris.util.steam import shortcut


class Game:
    id = "game-1"
    slug = "game"
    name = "Game"
    runner_name = "wine"


class TestSteamShortcut(unittest.TestCase):
    @patch.object(shortcut, "is_flatpak_lutris", return_value=True)
    @patch.object(shortcut.resources, "get_icon_path", return_value="icon")
    def test_flatpak_shortcut_uses_utf8_locale(self, _get_icon_path, _is_flatpak):
        generated = shortcut.generate_shortcut(Game(), "default")

        self.assertEqual(
            generated["LaunchOptions"],
            "LC_ALL=C.UTF-8 %command% run net.lutris.Lutris "
            "lutris:rungameid/game-1/default",
        )
