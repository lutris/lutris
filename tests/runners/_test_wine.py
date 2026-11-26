"""Tests for the Wine runner."""

import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from lutris.runners import wine as wine_module
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestEnsureClientRunning(TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.prefix = temp_dir.name
        self.client_exe = os.path.join(self.prefix, "Battle.net.exe")
        with open(self.client_exe, "w", encoding="utf-8"):
            pass

    def test_client_runs_with_the_games_environment(self):
        # The client launches the game, which inherits the client's environment
        runner = wine_module.wine(prefix=self.prefix, wine_arch="win64")
        game_env = {"DXVK_HUD": "1"}
        with (
            patch.object(wine_module.wine, "get_env", return_value=game_env),
            patch.object(wine_module.wine, "get_executable", return_value="/usr/bin/wine"),
            patch.object(wine_module.system, "is_process_running", return_value=False),
            patch.object(wine_module, "wineexec") as wineexec,
            patch("time.sleep"),
        ):
            runner._ensure_client_running(self.client_exe)

        self.assertEqual(wineexec.call_args.kwargs["env"], game_env)
        self.assertIs(wineexec.call_args.kwargs["runner"], runner)

    def prelaunch(self, executable):
        runner = wine_module.wine(wine_arch="win64")
        runner.config.game_config["client_exe"] = self.client_exe
        with (
            # With no prefix, prelaunch() has nothing to set up but the client
            patch.object(wine_module.wine, "prefix_path", None),
            patch.object(wine_module.wine, "_ensure_client_running") as ensure_client_running,
        ):
            runner.prelaunch(executable)
        return ensure_client_running

    def test_prelaunch_for_the_game_starts_the_client(self):
        self.prelaunch(None).assert_called_once_with(self.client_exe)

    def test_prelaunch_for_the_client_itself_does_not_start_it_again(self):
        # Starting the client runs prelaunch() for it, via wineexec()
        self.prelaunch(self.client_exe).assert_not_called()

    def test_relative_client_exe_without_a_prefix_is_refused(self):
        runner = wine_module.wine(wine_arch="win64")
        runner.config.game_config["client_exe"] = "Battle.net.exe"
        with (
            patch.object(wine_module.wine, "prefix_path", None),
            patch.object(wine_module.wine, "_ensure_client_running") as ensure_client_running,
        ):
            with self.assertRaises(wine_module.MisconfigurationError):
                runner.prelaunch()
        ensure_client_running.assert_not_called()


class TestRunWineTerminal(TestCase):
    def working_dir(self, prefix_path, game_path):
        runner = wine_module.wine(wine_arch="win64")
        with (
            patch.object(wine_module.wine, "prefix_path", prefix_path),
            patch.object(wine_module.wine, "game_path", game_path),
            patch.object(wine_module.wine, "get_env", return_value={}),
            patch.object(wine_module.wine, "get_executable", return_value="/usr/bin/wine"),
            patch.object(wine_module, "open_wine_terminal") as open_wine_terminal,
        ):
            runner.run_wine_terminal()
        return open_wine_terminal.call_args.kwargs["working_dir"]

    def test_shell_starts_in_the_prefix(self):
        self.assertEqual(self.working_dir("/games/prefix", "/games/game"), "/games/prefix")

    def test_without_a_prefix_the_shell_starts_in_the_game_folder(self):
        self.assertEqual(self.working_dir(None, "/games/game"), "/games/game")

    def test_without_a_prefix_or_game_folder_the_shell_starts_at_home(self):
        self.assertEqual(self.working_dir(None, ""), os.path.expanduser("~"))
