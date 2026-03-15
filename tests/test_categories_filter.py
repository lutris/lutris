import os
import unittest
from lutris import settings
from lutris.database import games as games_db
from lutris.database import categories as categories_db
from lutris.database import schema
from lutris.util.test_config import setup_test_environment

setup_test_environment()

class TestCategoriesFilter(unittest.TestCase):
    def setUp(self):
        if os.path.exists(settings.DB_PATH):
            os.remove(settings.DB_PATH)
        schema.syncdb()

    def test_filter_by_category(self):
        game_id1 = games_db.add_game(name="Game1", runner="linux")
        game_id2 = games_db.add_game(name="Game2", runner="linux")
        
        cat_id = categories_db.add_category("TestCategory")
        categories_db.add_game_to_category(game_id1, cat_id)
        
        # Test get_game_ids_for_categories
        ids = categories_db.get_game_ids_for_categories(included_category_names=["TestCategory"])
        self.assertIn(game_id1, ids)
        self.assertNotIn(game_id2, ids)
        
        # Test games_db.get_games_by_ids
        games = games_db.get_games_by_ids(ids)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["name"], "Game1")

    def test_filter_by_category_and_installed(self):
        game_id1 = games_db.add_game(name="Game1", runner="linux", installed=1)
        game_id2 = games_db.add_game(name="Game2", runner="linux", installed=0)
        
        cat_id = categories_db.add_category("TestCategory")
        categories_db.add_game_to_category(game_id1, cat_id)
        categories_db.add_game_to_category(game_id2, cat_id)
        
        ids = categories_db.get_game_ids_for_categories(included_category_names=["TestCategory"])
        games = games_db.get_games_by_ids(ids)
        self.assertEqual(len(games), 2)
        
        installed_games = [g for g in games if g["installed"]]
        self.assertEqual(len(installed_games), 1)
        self.assertEqual(installed_games[0]["name"], "Game1")
