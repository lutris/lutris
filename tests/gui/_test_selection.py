from unittest import TestCase

from lutris.gui.selection import retained_game_ids


class TestRetainedGameIds(TestCase):
    def test_keeps_order(self):
        available = {"a", "b", "c"}
        self.assertEqual(retained_game_ids(["c", "a"], available.__contains__), ["c", "a"])

    def test_drops_unavailable_games(self):
        available = {"a"}
        self.assertEqual(retained_game_ids(["a", "b"], available.__contains__), ["a"])

    def test_drops_missing_id(self):
        available = {"a"}
        self.assertEqual(retained_game_ids([None, "a"], available.__contains__), ["a"])

    def test_removes_duplicates(self):
        available = {"a", "b"}
        self.assertEqual(retained_game_ids(["a", "a", "b"], available.__contains__), ["a", "b"])

    def test_empty_selection(self):
        self.assertEqual(retained_game_ids([], {"a"}.__contains__), [])
