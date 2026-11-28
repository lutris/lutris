"""Missing-games flag transitions (headless, no signals or database).

_apply_missing_status is exercised on a bare instance so importing the
module wires no global handlers; only the set logic is under test.
"""

import os
import tempfile
import unittest

from lutris.util.path_cache import MissingGames
from lutris.util.test_config import setup_test_environment

setup_test_environment()


def fresh_state(*flagged):
    """A MissingGames without running __init__ (no signal registration)."""
    state = MissingGames.__new__(MissingGames)
    state.missing_game_ids = set(flagged)
    return state


class TestApplyMissingStatus(unittest.TestCase):
    def test_dead_path_flags_game(self):
        state = fresh_state()
        missing_dir = tempfile.mkdtemp()
        dead = os.path.join(missing_dir, "no-such-game.exe")
        self.assertTrue(MissingGames._apply_missing_status(state, "7", dead))
        self.assertIn("7", state.missing_game_ids)

    def test_existing_path_clears_flag(self):
        state = fresh_state("7")
        with tempfile.NamedTemporaryFile() as known:
            self.assertTrue(MissingGames._apply_missing_status(state, "7", known.name))
        self.assertNotIn("7", state.missing_game_ids)

    def test_empty_path_drops_stale_flag(self):
        """An unconfigured game is unknown, not missing: stale flags go."""
        state = fresh_state("7")
        self.assertTrue(MissingGames._apply_missing_status(state, "7", ""))
        self.assertNotIn("7", state.missing_game_ids)

    def test_none_path_drops_stale_flag(self):
        state = fresh_state("7")
        self.assertTrue(MissingGames._apply_missing_status(state, "7", None))
        self.assertNotIn("7", state.missing_game_ids)

    def test_empty_path_on_clean_set_is_noop(self):
        state = fresh_state()
        self.assertFalse(MissingGames._apply_missing_status(state, "7", ""))
        self.assertNotIn("7", state.missing_game_ids)

    def test_unchanged_status_is_noop(self):
        state = fresh_state("7")
        missing_dir = tempfile.mkdtemp()
        dead = os.path.join(missing_dir, "no-such-game.exe")
        self.assertFalse(MissingGames._apply_missing_status(state, "7", dead))
        self.assertIn("7", state.missing_game_ids)


if __name__ == "__main__":
    unittest.main()
