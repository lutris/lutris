import os
import unittest

from lutris import settings
from lutris.database import games as games_db
from lutris.database import schema
from lutris.gui.views import COL_NOTES
from lutris.gui.views.store import GameStore
from lutris.services.base import LutrisCoverart
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestGameStoreNotes(unittest.TestCase):
    def setUp(self):
        if os.path.exists(settings.DB_PATH):
            os.remove(settings.DB_PATH)
        schema.syncdb()
        self.store = GameStore(None, LutrisCoverart())

    def test_store_has_game_notes(self):
        game_id = games_db.add_game(name="LutrisTest", runner="linux", notes="Add /x64 to the arguments")
        self.store.add_game(games_db.get_game_by_field(game_id, "id"))
        self.assertEqual(self.store.get_row_by_id(game_id)[COL_NOTES], "Add /x64 to the arguments")

    def test_store_updates_game_notes(self):
        game_id = games_db.add_game(name="LutrisTest", runner="linux")
        self.store.add_game(games_db.get_game_by_field(game_id, "id"))
        self.assertEqual(self.store.get_row_by_id(game_id)[COL_NOTES], "")
        games_db.update_existing(id=game_id, notes="Add /x64 to the arguments")
        changed_columns = self.store.update(games_db.get_game_by_field(game_id, "id"))
        self.assertIn(COL_NOTES, changed_columns)
        self.assertEqual(self.store.get_row_by_id(game_id)[COL_NOTES], "Add /x64 to the arguments")
