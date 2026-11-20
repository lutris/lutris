"""Tests for the checks the uninstall dialog makes before deleting game files."""

from unittest import TestCase

from lutris.database.games import add_game, delete_game
from lutris.gui.dialogs.uninstall_dialog import get_installed_games_in_directory
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestGamesInDirectory(TestCase):
    """Deleting a game's directory deletes every other game inside it, too."""

    def add_game(self, slug, directory, installed=1):
        game_id = add_game(name=slug, slug=slug, runner="linux", directory=directory, installed=installed)
        self.addCleanup(delete_game, game_id)
        return game_id

    def test_finds_games_in_and_under_the_directory(self):
        outer = self.add_game("outer", "/mnt/games")
        inner = self.add_game("inner", "/mnt/games/inner")
        self.add_game("elsewhere", "/mnt/other")
        self.add_game("lookalike", "/mnt/games-old")
        self.assertEqual(get_installed_games_in_directory("/mnt/games"), {outer, inner})

    def test_ignores_uninstalled_games_and_games_without_a_directory(self):
        self.add_game("uninstalled", "/mnt/games/uninstalled", installed=0)
        self.add_game("nowhere", "")
        self.assertEqual(get_installed_games_in_directory("/mnt/games"), set())
