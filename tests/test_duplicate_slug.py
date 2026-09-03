"""Ensure add_game() produces unique slugs to prevent coverart collision.

Regression test for duplicate slug bug: two different games could share the
same slug, so coverart/<slug>.png was shared (setting a poster on one
changed both).

Intentional behavior documented here:
- Creation (add_game) ALWAYS dedups: undertail, undertail-2, undertail-3, ...
- Rename does NOT auto-change slug (only creation guarantees uniqueness).
- No DB UNIQUE constraint (would break service imports on legacy dup DBs).
"""

import os
import unittest

from lutris import settings
from lutris.database import games as games_db
from lutris.database import schema
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestUniqueSlug(unittest.TestCase):
    def setUp(self):
        if os.path.exists(settings.DB_PATH):
            os.remove(settings.DB_PATH)
        schema.syncdb()

    def _slug_of(self, game_id):
        game = games_db.get_game_by_field(game_id, "id")
        assert game is not None
        return game["slug"]

    def test_duplicate_name_gets_unique_slug(self):
        first_id = games_db.add_game(name="Undertail", runner="linux")
        second_id = games_db.add_game(name="Undertail", runner="linux")
        self.assertEqual(self._slug_of(first_id), "undertail")
        self.assertEqual(self._slug_of(second_id), "undertail-2")

    def test_third_duplicate_goes_to_3(self):
        games_db.add_game(name="Undertail", runner="linux")
        games_db.add_game(name="Undertail", runner="linux")
        third_id = games_db.add_game(name="Undertail", runner="linux")
        self.assertEqual(self._slug_of(third_id), "undertail-3")

    def test_explicit_duplicate_slug_gets_suffixed(self):
        first_id = games_db.add_game(name="Plants vs Zombie", runner="linux", slug="undertail")
        second_id = games_db.add_game(name="Undertail", runner="linux", slug="undertail")
        self.assertEqual(self._slug_of(first_id), "undertail")
        self.assertEqual(self._slug_of(second_id), "undertail-2")

    def test_suffix_gap_is_skipped(self):
        """If base-2 is already taken, next add must go to -3 (loop, not single if)."""
        games_db.add_game(name="Undertail", runner="linux")
        games_db.add_game(name="Undertail", runner="linux", slug="undertail-2")
        third_id = games_db.add_game(name="Undertail", runner="linux")
        self.assertEqual(self._slug_of(third_id), "undertail-3")

    def test_rename_keeps_slug(self):
        """Document intentional behavior: updating a game does not auto-change slug."""
        game_id = games_db.add_game(name="Undertail", runner="linux")
        games_db.add_or_update(id=game_id, name="Undertail Remastered", slug="undertail", runner="linux")
        game = games_db.get_game_by_field(game_id, "id")
        assert game is not None
        self.assertEqual(game["name"], "Undertail Remastered")
        self.assertEqual(game["slug"], "undertail")


if __name__ == "__main__":
    unittest.main()
