"""Tests for the database layer: query validation, query building, caching, bulk writes,
schema migration and concurrent access.

These tests build on the DatabaseTester fixture from tests._test_pga, which gives every test a
fresh database, but they only exercise the database layer itself rather than the GUI.
"""

import sqlite3
import threading
from unittest.mock import patch

from lutris import settings
from lutris.database import games as games_db
from lutris.database import schema, sql
from lutris.util.test_config import setup_test_environment
from tests._test_pga import DatabaseTester

setup_test_environment()


class TestIdentifierValidation(DatabaseTester):
    """Everything interpolated into a query must be a validated identifier."""

    def test_identifiers_are_plain_names_only(self):
        self.assertEqual(sql.validate_identifier("games"), "games")
        for name in ("", "1games", "ga-mes", "ga mes", "games;", "'games'", 'ga"mes', "ga'mes", None, 42):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    sql.validate_identifier(name)

    def test_field_names_are_checked_against_the_schema(self):
        self.assertEqual(sql.validate_field_name("games", "name"), "name")
        with self.assertRaises(ValueError):
            sql.validate_field_name("games", "not_a_column")
        # Tables that were never registered can only be checked syntactically.
        self.assertEqual(sql.validate_field_name("unregistered_table", "whatever"), "whatever")

    def test_field_expressions(self):
        self.assertEqual(sql.validate_field_expression("games", "*"), "*")
        self.assertEqual(sql.validate_field_expression("games", "COUNT(id)"), "COUNT(id)")
        self.assertEqual(sql.validate_field_expression("games", "count(*)"), "count(*)")
        with self.assertRaises(ValueError):
            sql.validate_field_expression("games", "COUNT(id) FROM games; --")
        with self.assertRaises(ValueError):
            sql.validate_field_expression("games", "DROP(id)")
        with self.assertRaises(ValueError):
            sql.validate_field_expression("games", "COUNT(not_a_column)")

    def test_column_types(self):
        self.assertEqual(sql.validate_column_type("TEXT UNIQUE"), "TEXT UNIQUE")
        with self.assertRaises(ValueError):
            sql.validate_column_type("TEXT); drop table games; --")

    def test_comparison_conditions(self):
        self.assertEqual(sql.create_comparison("games", "year", "<=", 2000), ("year <= ?", (2000,)))
        with self.assertRaises(ValueError):
            sql.create_comparison("games", "not_a_column", "=", 1)
        with self.assertRaises(ValueError):
            sql.create_comparison("games", "year", "<= 1 or 1=1", 2000)

    def test_filtered_query_rejects_unvalidated_fields(self):
        for arguments in (
            {"filters": {"name = 'x' or 1=1": "value"}},
            {"excludes": {"not_a_column": "value"}},
            {"searches": {"not_a_column": "value"}},
            {"searches": {"name": "value"}, "filters": {"unknown": 1}},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    sql.filtered_query(settings.DB_PATH, "games", **arguments)

    def test_filtered_query_rejects_unvalidated_table_and_sorts(self):
        with self.assertRaises(ValueError):
            sql.filtered_query(settings.DB_PATH, "games; drop table games")
        with self.assertRaises(ValueError):
            sql.filtered_query(settings.DB_PATH, "games", sorts=[("name", "ASC; drop table games")])
        with self.assertRaises(ValueError):
            sql.filtered_query(settings.DB_PATH, "games", sorts=[("not_a_column", "ASC")])

    def test_db_select_rejects_unvalidated_fields(self):
        with self.assertRaises(ValueError):
            sql.db_select(settings.DB_PATH, "games", fields=["name from games; --"])
        with self.assertRaises(ValueError):
            sql.db_select(settings.DB_PATH, "games", condition=("name or 1=1", "value"))

    def test_db_update_and_delete_reject_unvalidated_fields(self):
        with self.assertRaises(ValueError):
            sql.db_update(settings.DB_PATH, "games", {"name": "x"}, {"id or 1=1": 1})
        with self.assertRaises(ValueError):
            sql.db_delete(settings.DB_PATH, "games", "id; drop table games", 1)

    def test_db_insert_rejects_unvalidated_fields(self):
        with self.assertRaises(ValueError):
            sql.db_insert(settings.DB_PATH, "games", {"name) values ('x'); --": "y"})

    def test_db_update_requires_conditions(self):
        """Without conditions an update would silently rewrite the whole table."""
        with self.assertRaises(ValueError):
            sql.db_update(settings.DB_PATH, "games", {"name": "x"}, {})

    def test_add_fields_rejects_unvalidated_fields(self):
        with self.assertRaises(ValueError):
            sql.add_field(settings.DB_PATH, "games", {"name": "counter", "type": "INTEGER; drop table games"})
        with self.assertRaises(ValueError):
            sql.add_field(settings.DB_PATH, "games", {"name": "counter INTEGER); --", "type": "INTEGER"})

    def test_tables_are_still_usable_after_rejected_queries(self):
        game_id = games_db.add_game(name="A game", runner="linux")
        self.assertEqual(games_db.get_game_by_field(game_id, "id")["name"], "A game")
        self.assertEqual(games_db.get_game_count("runner", "linux"), 1)
        self.assertEqual(games_db.get_game_count("runner", "wine"), 0)

    def test_null_conditions(self):
        self.assertEqual(sql.create_null_check("games", "discord_id"), ("discord_id IS NULL", ()))
        self.assertEqual(sql.create_null_check("games", "discord_id", is_null=False), ("discord_id IS NOT NULL", ()))
        with self.assertRaises(ValueError):
            sql.create_null_check("games", "not_a_column")

    def test_registered_columns_are_known(self):
        self.assertIn("name", sql.get_table_columns("games") or frozenset())
        self.assertIsNone(sql.get_table_columns("not_a_table"))


class TestQueryBuilding(DatabaseTester):
    """The shared read path: filters, searches, sorts and result mapping."""

    def test_results_are_plain_dicts(self):
        games_db.add_game(name="A game", runner="linux")
        rows = sql.db_select(settings.DB_PATH, "games")
        self.assertEqual(type(rows[0]), dict)
        self.assertEqual(rows[0]["name"], "A game")

    def test_db_select_has_no_implicit_order(self):
        """db_select keeps returning rows in insertion order, unlike filtered_query."""
        games_db.add_game(name="Zebra", runner="linux")
        games_db.add_game(name="Aardvark", runner="linux")
        names = [game["name"] for game in sql.db_select(settings.DB_PATH, "games")]
        self.assertEqual(names, ["Zebra", "Aardvark"])
        slug_order = [game["name"] for game in sql.filtered_query(settings.DB_PATH, "games")]
        self.assertEqual(slug_order, ["Aardvark", "Zebra"])

    def test_db_select_with_an_iterable_condition(self):
        games_db.add_game(name="A game", runner="linux")
        games_db.add_game(name="B game", runner="linux")
        games_db.add_game(name="C game", runner="wine")
        rows = sql.db_select(settings.DB_PATH, "games", condition=("runner", {"linux"}))
        self.assertEqual(len(rows), 2)

    def test_db_select_with_a_none_condition_matches_nothing(self):
        """`field = NULL` is never true, and that historic behaviour is preserved."""
        games_db.add_game(name="A game", runner="linux")
        self.assertEqual(sql.db_select(settings.DB_PATH, "games", condition=("discord_id", None)), [])
        # NULL lookups are available through filters, which build `IS NULL` instead.
        self.assertEqual(len(sql.filtered_query(settings.DB_PATH, "games", filters={"discord_id": None})), 1)

    def test_filtered_query_sorts_by_the_given_fields(self):
        games_db.add_game(name="Older game", runner="linux", year=2000)
        games_db.add_game(name="Newer game", runner="linux", year=2010)
        games = games_db.get_games(sorts=[("year", "DESC")])
        self.assertEqual([game["name"] for game in games], ["Newer game", "Older game"])
        games = games_db.get_games(sorts=[("year", "ASC")])
        self.assertEqual([game["name"] for game in games], ["Older game", "Newer game"])

    def test_db_select_counts_rows_with_an_aggregate(self):
        games_db.add_game(name="A game", runner="linux")
        games_db.add_game(name="B game", runner="linux")
        rows = sql.db_select(settings.DB_PATH, "games", fields=["COUNT(*)"])
        self.assertEqual(rows[0]["COUNT(*)"], 2)


class TestGetGamesWhere(DatabaseTester):
    """get_games_where() conditions, including the conditions that mean 'nothing'."""

    def test_no_conditions_returns_an_empty_list(self):
        games_db.add_game(name="A game", runner="linux")
        self.assertEqual(games_db.get_games_where(), [])

    def test_unknown_field_raises(self):
        with self.assertRaises(ValueError):
            games_db.get_games_where(not_a_column="value")

    def test_unknown_suffix_raises(self):
        with self.assertRaises(ValueError):
            games_db.get_games_where(name__contains="game")

    def test_in_condition_matches_any_value(self):
        first_game = games_db.add_game(name="A game", runner="linux")
        second_game = games_db.add_game(name="B game", runner="linux")
        games_db.add_game(name="C game", runner="wine")
        found = games_db.get_games_where(id__in=[first_game, second_game])
        self.assertEqual({game["id"] for game in found}, {first_game, second_game})

    def test_empty_in_condition_matches_nothing(self):
        games_db.add_game(name="A game", runner="linux")
        self.assertEqual(games_db.get_games_where(id__in=[]), [])

    def test_in_condition_requires_an_iterable(self):
        with self.assertRaises(ValueError):
            games_db.get_games_where(id__in=1)

    def test_isnull_condition(self):
        games_db.add_game(name="A game", runner="linux")
        self.assertEqual(len(games_db.get_games_where(discord_id__isnull=True)), 1)
        self.assertEqual(games_db.get_games_where(discord_id__isnull=False), [])

    def test_lessthan_condition(self):
        games_db.add_game(name="A game", runner="linux", year=2000)
        games_db.add_game(name="B game", runner="linux", year=2010)
        found = games_db.get_games_where(year__lessthan=2005)
        self.assertEqual([game["name"] for game in found], ["A game"])

    def test_not_condition_excludes_rows_where_the_field_is_null(self):
        games_db.add_game(name="A game", runner="linux", platform="Linux")
        games_db.add_game(name="B game", runner="linux")
        found = games_db.get_games_where(platform__not="Linux")
        self.assertEqual(found, [])

    def test_conditions_are_combined(self):
        games_db.add_game(name="A game", runner="linux", installed=1)
        games_db.add_game(name="B game", runner="wine", installed=1)
        games_db.add_game(name="C game", runner="linux", installed=0)
        found = games_db.get_games_where(runner="linux", installed=1)
        self.assertEqual([game["name"] for game in found], ["A game"])

    def test_results_have_string_ids(self):
        game_id = games_db.add_game(name="A game", runner="linux")
        found = games_db.get_games_where(name="A game")
        self.assertEqual(found[0]["id"], game_id)
        self.assertEqual(type(found[0]["id"]), str)

    def test_lookups_by_ids_are_chunked(self):
        """SQLite only accepts 999 parameters per query, so ids are looked up in chunks."""
        game_ids = games_db.add_games_bulk(
            [{"name": "Game %s" % index, "slug": "game-%s" % index, "runner": "linux"} for index in range(1010)]
        )
        found = games_db.get_games_by_ids(game_ids)
        self.assertEqual(len(found), 1010)

    def test_get_game_by_field_returns_none_for_a_none_value(self):
        """A NULL lookup must not match the first row that happens to have a NULL field."""
        games_db.add_game(name="A game", runner="linux")
        self.assertIsNone(games_db.get_game_by_field(None, "installer_slug"))
        self.assertIsNone(games_db.get_game_by_field(None, "id"))

    def test_get_game_by_field_rejects_other_fields(self):
        with self.assertRaises(ValueError):
            games_db.get_game_by_field("linux", "runner")


class TestServiceCache(DatabaseTester):
    """The cached service game lists must never outlive the data they mirror."""

    def test_installed_games_are_listed_by_slug(self):
        games_db.add_game(name="Installed game", runner="linux", installed=1)
        self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])

    def test_uninstalled_games_are_not_listed(self):
        games_db.add_game(name="Uninstalled game", runner="linux", installed=0)
        self.assertEqual(games_db.get_service_games("lutris"), [])

    def test_cache_is_invalidated_by_an_insert(self):
        self.assertEqual(games_db.get_service_games("lutris"), [])
        games_db.add_game(name="Installed game", runner="linux", installed=1)
        self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])

    def test_cache_is_invalidated_by_a_delete(self):
        game_id = games_db.add_game(name="Installed game", runner="linux", installed=1)
        self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])
        games_db.delete_game(game_id)
        self.assertEqual(games_db.get_service_games("lutris"), [])

    def test_cache_is_invalidated_by_an_update(self):
        game_id = games_db.add_game(name="A game", runner="linux", installed=0)
        self.assertEqual(games_db.get_service_games("lutris"), [])
        sql.db_update(settings.DB_PATH, "games", {"installed": 1}, {"id": game_id})
        self.assertEqual(games_db.get_service_games("lutris"), ["a-game"])

    def test_cache_is_invalidated_by_writes_from_other_modules(self):
        """A service writing to the database must invalidate the cache as well."""
        self.assertEqual(games_db.get_service_games("steam"), [])
        sql.db_insert(
            settings.DB_PATH,
            "games",
            {"name": "Steam game", "slug": "steam-game", "service": "steam", "service_id": "42", "installed": 1},
        )
        self.assertEqual(games_db.get_service_games("steam"), ["42"])

    def test_cache_is_invalidated_by_a_bulk_insert(self):
        self.assertEqual(games_db.get_service_games("lutris"), [])
        games_db.add_games_bulk([{"name": "Installed game", "slug": "installed-game", "installed": 1}])
        self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])

    def test_the_database_is_only_queried_once_per_cache_lifetime(self):
        games_db.add_game(name="Installed game", runner="linux", installed=1)
        with patch.object(games_db, "get_games", wraps=games_db.get_games) as get_games:
            games_db.get_service_games("lutris")
            games_db.get_service_games("lutris")
        self.assertEqual(get_games.call_count, 1)

    def test_cache_is_invalidated_by_raw_sql_writes(self):
        """A transaction that changes rows invalidates the cache, helpers or not."""
        self.assertEqual(games_db.get_service_games("lutris"), [])
        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(
                cursor,
                "insert into games (name, slug, installed) values (?, ?, ?)",
                ("Raw game", "raw-game", 1),
            )
        self.assertEqual(games_db.get_service_games("lutris"), ["raw-game"])

    def test_a_read_transaction_keeps_the_cache(self):
        """A transaction that changes no rows must not report a data change."""
        games_db.add_game(name="Installed game", runner="linux", installed=1)
        with patch.object(games_db, "get_games", wraps=games_db.get_games) as get_games:
            self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])
            with sql.db_cursor(settings.DB_PATH) as cursor:
                cursor.execute("select * from games")
            # Still served from the cache, so the database was not queried a second time.
            self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])
        self.assertEqual(get_games.call_count, 1)

    def test_callers_cannot_modify_the_cache(self):
        games_db.add_game(name="Installed game", runner="linux", installed=1)
        listed_games = games_db.get_service_games("lutris")
        listed_games.append("something else")
        self.assertEqual(games_db.get_service_games("lutris"), ["installed-game"])


class TestAddGamesBulk(DatabaseTester):
    """Bulk inserts must run in one transaction and never leave a partial batch."""

    @staticmethod
    def make_games(count: int) -> list[dict]:
        return [{"name": "Game %s" % index, "slug": "game-%s" % index, "runner": "linux"} for index in range(count)]

    def test_every_game_is_inserted(self):
        game_ids = games_db.add_games_bulk(self.make_games(20))
        self.assertEqual(len(game_ids), 20)
        self.assertEqual(len(set(game_ids)), 20)
        self.assertEqual(len(games_db.get_games()), 20)

    def test_returned_ids_match_the_inserted_games(self):
        game_ids = games_db.add_games_bulk(self.make_games(3))
        names = [games_db.get_game_by_field(game_id, "id")["name"] for game_id in game_ids]
        self.assertEqual(names, ["Game 0", "Game 1", "Game 2"])

    def test_no_games_inserts_nothing(self):
        self.assertEqual(games_db.add_games_bulk([]), [])
        self.assertEqual(games_db.get_games(), [])

    def test_rows_with_different_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            games_db.add_games_bulk([{"name": "A game"}, {"name": "B game", "slug": "b-game"}])
        self.assertEqual(games_db.get_games(), [])

    def test_a_failing_row_rolls_back_the_whole_batch(self):
        schema.create_table(
            "bulk_test",
            [
                {"name": "id", "type": "INTEGER", "indexed": True},
                {"name": "slug", "type": "TEXT", "unique": True},
            ],
        )
        with self.assertRaises(sqlite3.IntegrityError):
            sql.db_insert_many(settings.DB_PATH, "bulk_test", [{"slug": "same"}, {"slug": "same"}])
        # The successful insert of the first row must have been rolled back with the second.
        self.assertEqual(sql.db_select(settings.DB_PATH, "bulk_test"), [])

    def test_bulk_inserts_one_transaction(self):
        """The whole batch is committed once, not once per row."""
        with patch("lutris.database.sql.db_cursor", wraps=sql.db_cursor) as db_cursor:
            games_db.add_games_bulk(self.make_games(10))
        self.assertEqual(db_cursor.call_count, 1)


class TestMigration(DatabaseTester):
    """Schema migration only adds what is missing, and does so safely."""

    def setUp(self):
        super().setUp()
        self.table_name = "migration_test"
        self.reference_schema = [
            {"name": "id", "type": "INTEGER", "indexed": True},
            {"name": "name", "type": "TEXT"},
        ]
        schema.create_table(self.table_name, self.reference_schema)

    def test_missing_columns_are_added(self):
        extended_schema = self.reference_schema + [
            {"name": "counter", "type": "INTEGER"},
            {"name": "comment", "type": "TEXT"},
        ]
        self.assertEqual(schema.migrate(self.table_name, extended_schema), ["counter", "comment"])
        self.assertEqual(self.column_names(), ["id", "name", "counter", "comment"])

    def test_migration_is_idempotent(self):
        extended_schema = self.reference_schema + [{"name": "counter", "type": "INTEGER"}]
        self.assertEqual(schema.migrate(self.table_name, extended_schema), ["counter"])
        self.assertEqual(schema.migrate(self.table_name, extended_schema), [])

    def test_migration_keeps_columns_that_are_not_in_the_schema(self):
        """A column added by a newer Lutris (or a legacy one) must never be dropped."""
        sql.add_field(settings.DB_PATH, self.table_name, {"name": "legacy", "type": "INTEGER"})
        schema.migrate(self.table_name, self.reference_schema)
        self.assertIn("legacy", self.column_names())

    def test_migration_creates_a_missing_table(self):
        self.assertEqual(schema.migrate("new_table", self.reference_schema), [])
        self.assertEqual([field["name"] for field in schema.get_schema("new_table")], ["id", "name"])

    def test_migrated_unique_column_gets_a_unique_index(self):
        extended_schema = self.reference_schema + [{"name": "uri", "type": "TEXT", "unique": True}]
        schema.migrate(self.table_name, extended_schema)
        sql.db_insert(settings.DB_PATH, self.table_name, {"name": "A", "uri": "same"})
        with self.assertRaises(sqlite3.IntegrityError):
            sql.db_insert(settings.DB_PATH, self.table_name, {"name": "B", "uri": "same"})

    def test_migrated_columns_can_be_used_right_away(self):
        """A column added by a migration is whitelisted, so queries can refer to it."""
        extended_schema = self.reference_schema + [{"name": "counter", "type": "INTEGER"}]
        schema.migrate(self.table_name, extended_schema)
        sql.db_insert(settings.DB_PATH, self.table_name, {"name": "A", "counter": 3})
        self.assertEqual(len(sql.filtered_query(settings.DB_PATH, self.table_name, filters={"counter": 3})), 1)

    def test_migration_rejects_invalid_field_names(self):
        extended_schema = self.reference_schema + [{"name": "counter TEXT); drop table games; --", "type": "TEXT"}]
        with self.assertRaises(ValueError):
            schema.migrate(self.table_name, extended_schema)

    def test_schema_lookup_rejects_invalid_table_names(self):
        with self.assertRaises(ValueError):
            schema.get_schema("games; drop table games")

    def column_names(self) -> list[str]:
        return [field["name"] for field in schema.get_schema(self.table_name)]


class TestConcurrency(DatabaseTester):
    """Writes are serialized, reads run alongside them."""

    def test_wal_journaling_is_enabled(self):
        with sql.db_read_cursor(settings.DB_PATH) as cursor:
            journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(journal_mode.lower(), "wal")

    def test_reads_run_while_another_thread_holds_the_write_lock(self):
        games_db.add_game(name="A game", runner="linux")
        lock_held = threading.Event()
        release_lock = threading.Event()
        read_names = []
        reader_alive = []

        def hold_write_lock():
            with sql.db_cursor(settings.DB_PATH) as cursor:
                sql.cursor_execute(cursor, "update games set name=? where 1=1", ("Renamed",))
                lock_held.set()
                release_lock.wait(timeout=30)

        def read_games():
            lock_held.wait(timeout=30)
            read_names.extend(game["name"] for game in games_db.get_games())
            reader_alive.append(True)

        writer_thread = threading.Thread(target=hold_write_lock)
        reader_thread = threading.Thread(target=read_games)
        writer_thread.start()
        reader_thread.start()
        try:
            reader_thread.join(timeout=10)
            self.assertFalse(reader_thread.is_alive(), "the read blocked on the write lock")
            # The uncommitted update is not visible to the reader.
            self.assertEqual(read_names, ["A game"])
        finally:
            release_lock.set()
            writer_thread.join(timeout=30)

    def test_reads_and_writes_from_several_threads(self):
        errors = []
        stop_reading = threading.Event()
        writers = 3
        games_per_writer = 10

        def write_games(writer_index):
            try:
                for game_index in range(games_per_writer):
                    games_db.add_game(name="Game %s-%s" % (writer_index, game_index), runner="linux", installed=1)
            except Exception as err:  # pylint: disable=broad-except
                errors.append(err)

        def read_games():
            try:
                while not stop_reading.is_set():
                    games_db.get_games()
                    games_db.get_games_where(installed=1)
                    games_db.get_service_games("lutris")
                    schema.get_schema("games")
            except Exception as err:  # pylint: disable=broad-except
                errors.append(err)

        reader_threads = [threading.Thread(target=read_games) for _ in range(3)]
        writer_threads = [threading.Thread(target=write_games, args=(index,)) for index in range(writers)]
        for thread in reader_threads + writer_threads:
            thread.start()
        try:
            for thread in writer_threads:
                thread.join(timeout=60)
        finally:
            stop_reading.set()
            for thread in reader_threads:
                thread.join(timeout=60)

        self.assertEqual(errors, [])
        self.assertEqual(len(games_db.get_games(filters={"installed": 1})), writers * games_per_writer)
