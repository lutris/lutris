#!/usr/bin/python
import unittest
import os
from sqlite3 import IntegrityError, OperationalError
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
        pga.syncdb()
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

    def test_can_filter_by_installed_games(self):
        pga.add_game(name="installed_game", runner="Linux", installed=1)
        pga.add_game(name="bang", runner="Linux", installed=0)
        game_list = pga.get_games(filter_installed=True)
        print game_list
        self.assertEqual(len(game_list), 1)
        self.assertEqual(game_list[0]['name'], 'installed_game')

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
        text_field = pga.field_to_string('name', 'TEXT')
        self.assertEqual(text_field, "name TEXT")

        id_field = pga.field_to_string('id', 'INTEGER', indexed=True)
        self.assertEqual(id_field, "id INTEGER PRIMARY KEY")

    def test_can_create_table(self):
        fields = [
            {'name': 'id', 'type': 'INTEGER', 'indexed': True},
            {'name': 'name', 'type': 'TEXT'}
        ]
        pga.create_table('testing', fields)
        sql.db_insert(TEST_PGA_PATH, 'testing', {'name': "testok"})
        results = sql.db_select(TEST_PGA_PATH, 'testing',
                                fields=['id', 'name'])
        self.assertEqual(results[0]['name'], "testok")


class TestMigration(DatabaseTester):
    def setUp(self):
        super(TestMigration, self).setUp()
        pga.syncdb()
        self.tablename = "basetable"
        self.schema = [
            {
                'name': 'id',
                'type': 'INTEGER',
                'indexed': True
            },
            {
                'name': 'name',
                'type': 'TEXT',
            }
        ]

    def create_table(self):
        pga.create_table(self.tablename, self.schema)

    def test_get_schema(self):
        self.create_table()
        schema = pga.get_schema(self.tablename)
        self.assertEqual(schema[0]['name'], 'id')
        self.assertEqual(schema[0]['type'], 'INTEGER')
        self.assertEqual(schema[1]['name'], 'name')
        self.assertEqual(schema[1]['type'], 'TEXT')

    def test_add_field(self):
        self.create_table()
        field = {
            'name': 'counter',
            'type': 'INTEGER'
        }
        pga.add_field(self.tablename, field)
        schema = pga.get_schema(self.tablename)
        self.assertEqual(schema[2]['name'], 'counter')
        self.assertEqual(schema[2]['type'], 'INTEGER')

    def test_cant_add_existing_field(self):
        self.create_table()
        field = {
            'name': 'name',
            'type': 'TEXT'
        }
        with self.assertRaises(OperationalError):
            pga.add_field(self.tablename, field)

    def test_cant_create_empty_table(self):
        with self.assertRaises(OperationalError):
            pga.create_table('emptytable', [])

    def test_can_know_if_table_exists(self):
        self.create_table()
        self.assertTrue(pga.get_schema(self.tablename))
        self.assertFalse(pga.get_schema('notatable'))

    def test_can_migrate(self):
        self.create_table()
        self.schema.append({'name': 'new_field', 'type': 'TEXT'})
        migrated = pga.migrate(self.tablename, self.schema)
        schema = pga.get_schema(self.tablename)
        self.assertEqual(schema[2]['name'], 'new_field')
        self.assertEqual(migrated, ['new_field'])

    def test_does_set_installed_games(self):
        pga.add_game(name="some game", runner='linux', directory="/home")
        pga.set_installed_games()
        test_game = pga.get_games()[0]
        self.assertEqual(test_game['installed'], 1)
