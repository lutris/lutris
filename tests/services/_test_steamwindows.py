"""Tests for the Steam for Windows service."""

from unittest import TestCase
from unittest.mock import patch

from lutris.services import steam
from lutris.services.steamwindows import SteamWindowsService
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestAddInstalledGames(TestCase):
    def test_native_steam_games_are_left_alone(self):
        # The Windows client's steamapps has nothing, as when it isn't installed
        with (
            patch.object(SteamWindowsService, "steamapps_paths", []),
            patch.object(steam, "get_games", return_value=[{"id": "1", "service_id": "440"}]) as get_games,
            patch.object(steam, "Game") as game,
            patch.object(steam, "sync_media"),
        ):
            SteamWindowsService().add_installed_games()

        get_games.assert_not_called()
        game.return_value.uninstall.assert_not_called()
