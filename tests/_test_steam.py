"""Tests for Steam shortcut generation."""

import unittest
from unittest.mock import patch

from lutris.util import resources
from lutris.util.steam import config as steam_config
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


class TestSteamUsers(unittest.TestCase):
    """Picking which Steam account is the active one"""

    ACCOUNTS = {
        "users": {
            "76561197960287930": {"AccountName": "older", "Timestamp": "1700000000"},
            "76561197960287931": {"AccountName": "newer", "Timestamp": "1800000000"},
        }
    }

    def get_users(self, config):
        with patch.object(steam_config, "read_user_config", return_value=config):
            return steam_config.get_steam_users()

    def test_most_recent_flag_wins_when_steam_writes_it(self):
        config = {"users": dict(self.ACCOUNTS["users"])}
        config["users"]["76561197960287930"] = dict(config["users"]["76561197960287930"], MostRecent="1")
        self.assertEqual(self.get_users(config)[0]["AccountName"], "older")

    def test_falls_back_to_the_login_timestamp(self):
        """Current Steam no longer writes MostRecent, which left file order deciding."""
        self.assertEqual(self.get_users(self.ACCOUNTS)[0]["AccountName"], "newer")

    def test_accounts_without_a_timestamp_sort_last(self):
        config = {"users": dict(self.ACCOUNTS["users"], **{"76561197960287932": {"AccountName": "undated"}})}
        self.assertEqual(self.get_users(config)[-1]["AccountName"], "undated")

    def test_a_missing_optional_key_is_not_logged(self):
        with self.assertNoLogs("lutris.util.log", level="WARNING"):
            self.get_users(self.ACCOUNTS)

    def test_a_missing_key_still_warns_by_default(self):
        with self.assertLogs("lutris.util.log", level="WARNING"):
            steam_config.get_config_value({"AccountName": "x"}, "nope")
