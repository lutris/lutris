"""Tests for Steam shortcut generation."""

import unittest
from unittest.mock import patch

from lutris.util import resources
from lutris.util.steam import shortcut


class Game:
    id = "game-1"
    slug = "game"
    name = "Game"
    runner_name = "wine"


class TestSteamShortcut(unittest.TestCase):
    @patch.object(shortcut, "is_flatpak_lutris", return_value=True)
    @patch.object(resources, "get_icon_path", return_value="icon")
    def test_flatpak_shortcut_uses_utf8_locale(self, _get_icon_path, _is_flatpak):
        generated = shortcut.generate_shortcut(Game(), "default")

        self.assertEqual(
            generated["LaunchOptions"],
            "LC_ALL=C.UTF-8 %command% run net.lutris.Lutris lutris:rungameid/game-1/default",
        )
        # The Exe must stay put; Steam derives the non-Steam AppID from it.
        self.assertEqual(generated["Exe"], '"/usr/bin/flatpak"')

    @patch.object(shortcut, "is_flatpak_lutris", return_value=False)
    @patch.object(resources, "get_icon_path", return_value="icon")
    def test_non_flatpak_shortcut_is_unprefixed(self, _get_icon_path, _is_flatpak):
        generated = shortcut.generate_shortcut(Game(), "default")

        self.assertEqual(generated["LaunchOptions"], "lutris:rungameid/game-1/default")
        self.assertEqual(generated["Exe"], '"lutris"')
