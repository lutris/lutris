#!/usr/bin/python
import unittest
import os
from sqlite3 import IntegrityError
from lutris import pga
from lutris.util import sql

TEST_PGA_PATH = os.path.join(os.path.dirname(__file__), 'pga.db')


class DatabaseTester(unittest.TestCase):
    def setUp(self):
        pga.PGA_DB = TEST_PGA_PATH
        if os.path.exists(TEST_PGA_PATH):
            os.remove(TEST_PGA_PATH)

    def tearDown(self):
        if os.path.exists(TEST_PGA_PATH):
            os.remove(TEST_PGA_PATH)


class TestPersonnalGameArchive(DatabaseTester):
    def setUp(self):
        super(TestPersonnalGameArchive, self).setUp()
        pga.create()
        pga.add_game(name="LutrisTest", runner="Linux")

    def test_add_game(self):
        game_list = pga.get_games()
        game_names = [item['name'] for item in game_list]
        self.assertTrue("LutrisTest" in game_names)

    def test_delete_game(self):
        pga.delete_game("lutristest")
        game_list = pga.get_games()
        self.assertEqual(len(game_list), 0)
        pga.add_game(name="LutrisTest", runner="Linux")

    def test_get_game_list(self):
        game_list = pga.get_games()
        self.assertEqual(game_list[0]['slug'], 'lutristest')
        self.assertEqual(game_list[0]['name'], 'LutrisTest')
        self.assertEqual(game_list[0]['runner'], 'Linux')

    def test_filter(self):
        pga.add_game(name="foobar", runner="Linux")
        pga.add_game(name="bang", runner="Linux")
        game_list = pga.get_games(name_filter='bang')
        self.assertEqual(len(game_list), 1)
        self.assertEqual(game_list[0]['name'], 'bang')

    def test_game_slugs_must_be_unique(self):
        pga.add_game(name="unique game", runner="Linux")
        with self.assertRaises(IntegrityError):
            pga.add_game(name="unique game", runner="Linux")

    def test_game_with_same_slug_is_updated(self):
        pga.add_game(name="some game", runner="linux")
        game = pga.get_game_by_slug("some-game")
        self.assertFalse(game['directory'])
        pga.add_or_update(name="some game", runner='linux', directory="/foo")
        game = pga.get_game_by_slug("some-game")
        self.assertEqual(game['directory'], '/foo')


class TestDbCreator(DatabaseTester):
    def test_can_generate_fields(self):
        text_field = pga.create_field('name', 'TEXT')
        self.assertEqual(text_field, "name TEXT")

        id_field = pga.create_field('id', 'INTEGER', indexed=True)
        self.assertEqual(id_field, "id INTEGER PRIMARY KEY")

    def test_can_create_table(self):
        fields = [
            {'name': 'id', 'ftype': 'INTEGER', 'indexed': True},
            {'name': 'name', 'ftype': 'TEXT'}
        ]
        pga.create_table('testing', fields)
        sql.db_insert(TEST_PGA_PATH, 'testing', {'name': "testok"})
        results = sql.db_select(TEST_PGA_PATH, 'testing')
        self.assertEqual(results[0]['name'], "testok")


class TestMigration(DatabaseTester):
    def test_get_schema(self):
        schema = pga.get_schema('games')
        print schema
