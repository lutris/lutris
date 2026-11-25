"""Tests for downloading a Steam game as part of an install script."""

from unittest import TestCase
from unittest.mock import patch

from lutris.installer.steam_installer import SteamInstaller
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestCancelSteamInstall(TestCase):
    def test_cancelling_tells_steam_which_game_to_stop(self):
        installer = SteamInstaller("$STEAM:620:.", "steam_game")
        runner = installer.runner
        with (
            patch.object(runner, "get_game_path_from_appid", return_value=""),
            patch("lutris.installer.steam_installer.AsyncCall"),
            patch("lutris.installer.steam_installer.schedule_repeating_at_idle"),
        ):
            installer.install_steam_game()

        with (
            patch.object(runner, "is_installed", return_value=True),
            patch.object(runner, "get_command", return_value=["steam"]),
            patch("lutris.runners.steam.MonitoredCommand") as monitored_command,
        ):
            installer.stop_func()

        self.assertEqual(monitored_command.call_args.args[0], ["steam", "steam://uninstall/620"])
