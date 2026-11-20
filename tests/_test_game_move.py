"""Tests for moving a game's files to another folder."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lutris import settings
from lutris.config import write_game_config
from lutris.database import games, schema
from lutris.exceptions import InvalidGameMoveError
from lutris.game import Game


class TestMoveGame(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name, value in {"DB_PATH": str(self.root / "pga.db"), "CONFIG_DIR": str(self.root)}.items():
            patcher = patch.object(settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        schema.syncdb()
        (self.root / "games").mkdir()

        self.old = self.root / "library" / "doom"
        self.old.mkdir(parents=True)
        (self.old / "doom.wad").write_text("the game", encoding="utf-8")
        # Another game's folder, whose name starts with this one's
        self.neighbour = self.root / "library" / "doom2"
        self.neighbour.mkdir()
        self.destination = self.root / "moved"
        self.destination.mkdir()

        config = {"game": {"main_file": str(self.old / "doom.wad"), "files": [str(self.neighbour / "extra.wad")]}}
        self.game_id = games.add_game(
            name="Doom",
            slug="doom",
            runner="linux",
            installed=1,
            directory=str(self.old),
            configpath=write_game_config("doom", config),
        )

    def move(self):
        return Game(self.game_id).move(str(self.destination), no_signal=True)

    def get_directory(self):
        return games.get_game_by_field(self.game_id, "id")["directory"]

    def get_game_config(self):
        return Game(self.game_id).config.game_level["game"]

    def test_game_and_its_config_move_together(self):
        target = self.destination / "doom"
        self.assertEqual(self.move(), str(target))
        self.assertTrue((target / "doom.wad").is_file())
        self.assertFalse(self.old.exists())
        self.assertEqual(self.get_directory(), str(target))
        self.assertEqual(self.get_game_config()["main_file"], str(target / "doom.wad"))

    def test_paths_that_only_start_with_the_old_location_are_kept(self):
        self.move()
        self.assertEqual(self.get_game_config()["files"], [str(self.neighbour / "extra.wad")])

    def test_existing_destination_is_refused_and_nothing_changes(self):
        (self.destination / "doom").mkdir()
        with self.assertRaises(InvalidGameMoveError):
            self.move()
        self.assertTrue((self.old / "doom.wad").is_file())
        self.assertEqual(self.get_directory(), str(self.old))
        self.assertEqual(self.get_game_config()["main_file"], str(self.old / "doom.wad"))

    def test_failed_move_is_reported_and_the_game_keeps_its_location(self):
        with patch("lutris.game.shutil.move", side_effect=OSError("No space left on device")):
            with self.assertRaises(OSError):
                self.move()
        self.assertEqual(self.get_directory(), str(self.old))
        self.assertEqual(self.get_game_config()["main_file"], str(self.old / "doom.wad"))
