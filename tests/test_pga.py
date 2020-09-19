import unittest
import os
from sqlite3 import OperationalError
from lutris.database import schema
from lutris.database import games as games_db
from lutris.database import sql

TEST_PGA_PATH = os.path.join(os.path.dirname(__file__), 'pga.db')


class DatabaseTester(unittest.TestCase):
    def setUp(self):
        schema.PGA_DB = TEST_PGA_PATH
        games_db.PGA_DB = TEST_PGA_PATH
        if os.path.exists(TEST_PGA_PATH):
            os.remove(TEST_PGA_PATH)
        schema.syncdb()

    def tearDown(self):
        if os.path.exists(TEST_PGA_PATH):
            os.remove(TEST_PGA_PATH)


class TestPersonnalGameArchive(DatabaseTester):
    def setUp(self):
        super(TestPersonnalGameArchive, self).setUp()
        self.game_id = games_db.add_game(name="LutrisTest", runner="Linux")

    def test_add_game(self):
        game_list = games_db.get_games()
        game_names = [item['name'] for item in game_list]
        self.assertTrue("LutrisTest" in game_names)

    def test_delete_game(self):
        games_db.delete_game(self.game_id)
        game_list = games_db.get_games()
        self.assertEqual(len(game_list), 0)
        self.game_id = games_db.add_game(name="LutrisTest", runner="Linux")

    def test_get_game_list(self):
        game_list = games_db.get_games()
        self.assertEqual(game_list[0]['id'], self.game_id)
        self.assertEqual(game_list[0]['slug'], 'lutristest')
        self.assertEqual(game_list[0]['name'], 'LutrisTest')
        self.assertEqual(game_list[0]['runner'], 'Linux')

    def test_filter(self):
        games_db.add_game(name="foobar", runner="Linux")
        games_db.add_game(name="bang", runner="Linux")
        game_list = games_db.get_games(searches={"name": 'bang'})
        self.assertEqual(len(game_list), 1)
        self.assertEqual(game_list[0]['name'], 'bang')

    def test_can_filter_by_installed_games(self):
        games_db.add_game(name="installed_game", runner="Linux", installed=1)
        games_db.add_game(name="bang", runner="Linux", installed=0)
        game_list = games_db.get_games(filters={'installed': 1})
        self.assertEqual(len(game_list), 1)
        self.assertEqual(game_list[0]['name'], 'installed_game')

    def test_game_with_same_slug_is_updated(self):
        games_db.add_game(name="some game", runner="linux")
        game = games_db.get_game_by_field("some-game", "slug")
        self.assertFalse(game['directory'])
        games_db.add_or_update(name="some game", runner='linux', directory="/foo")
        game = games_db.get_game_by_field("some-game", "slug")
        self.assertEqual(game['directory'], '/foo')


class TestDbCreator(DatabaseTester):
    def test_can_generate_fields(self):
        text_field = schema.field_to_string('name', 'TEXT')
        self.assertEqual(text_field, "name TEXT")

        id_field = schema.field_to_string('id', 'INTEGER', indexed=True)
        self.assertEqual(id_field, "id INTEGER PRIMARY KEY")

    def test_can_create_table(self):
        fields = [
            {'name': 'id', 'type': 'INTEGER', 'indexed': True},
            {'name': 'name', 'type': 'TEXT'}
        ]
        schema.create_table('testing', fields)
        sql.db_insert(TEST_PGA_PATH, 'testing', {'name': "testok"})
        results = sql.db_select(TEST_PGA_PATH, 'testing',
                                fields=['id', 'name'])
        self.assertEqual(results[0]['name'], "testok")


class TestMigration(DatabaseTester):
    def setUp(self):
        super(TestMigration, self).setUp()
        schema.syncdb()
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
        schema.create_table(self.tablename, self.schema)

    def test_get_schema(self):
        self.create_table()
        _schema = schema.get_schema(self.tablename)
        self.assertEqual(_schema[0]['name'], 'id')
        self.assertEqual(_schema[0]['type'], 'INTEGER')
        self.assertEqual(_schema[1]['name'], 'name')
        self.assertEqual(_schema[1]['type'], 'TEXT')

    def test_add_field(self):
        self.create_table()
        field = {
            'name': 'counter',
            'type': 'INTEGER'
        }
        sql.add_field(TEST_PGA_PATH, self.tablename, field)
        _schema = schema.get_schema(self.tablename)
        self.assertEqual(_schema[2]['name'], 'counter')
        self.assertEqual(_schema[2]['type'], 'INTEGER')

    def test_cant_add_existing_field(self):
        self.create_table()
        field = {
            'name': 'name',
            'type': 'TEXT'
        }
        with self.assertRaises(OperationalError):
            sql.add_field(TEST_PGA_PATH, self.tablename, field)

    def test_cant_create_empty_table(self):
        with self.assertRaises(OperationalError):
            schema.create_table('emptytable', [])

    def test_can_know_if_table_exists(self):
        self.create_table()
        self.assertTrue(schema.get_schema(self.tablename))
        self.assertFalse(schema.get_schema('notatable'))

    def test_can_migrate(self):
        self.create_table()
        self.schema.append({'name': 'new_field', 'type': 'TEXT'})
        migrated = schema.migrate(self.tablename, self.schema)
        _schema = schema.get_schema(self.tablename)
        self.assertEqual(_schema[2]['name'], 'new_field')
        self.assertEqual(migrated, ['new_field'])
