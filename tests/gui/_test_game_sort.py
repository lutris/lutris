from datetime import datetime
from unittest import TestCase

from lutris.gui import game_sort
from lutris.gui.views import COL_NAME, COL_SORTNAME


class FakeService:
    """A service whose release date is enough to fill in a missing year."""

    id = "fake"

    def get_game_release_date(self, game):
        return "2011-05-01"


class TestNormalizeViewSorting(TestCase):
    def test_defaults_to_name(self):
        self.assertEqual(game_sort.normalize_view_sorting(None), "name")

    def test_strips_text_suffix(self):
        self.assertEqual(game_sort.normalize_view_sorting("lastplayed_text"), "lastplayed")

    def test_leaves_a_plain_sort_alone(self):
        self.assertEqual(game_sort.normalize_view_sorting("year"), "year")


class TestConvertSortValue(TestCase):
    def test_year_accepts_many_forms(self):
        self.assertEqual(game_sort.convert_sort_value(2014, "year"), 2014)
        self.assertEqual(game_sort.convert_sort_value("2014", "year"), 2014)
        self.assertEqual(game_sort.convert_sort_value("2014-03-01", "year"), 2014)
        self.assertEqual(game_sort.convert_sort_value(datetime(2014, 3, 1), "year"), 2014)

    def test_unparseable_year_is_none(self):
        self.assertIsNone(game_sort.convert_sort_value("nonsense", "year"))
        self.assertIsNone(game_sort.convert_sort_value("", "year"))

    def test_name_is_a_string(self):
        self.assertEqual(game_sort.convert_sort_value("Wine Game", "name"), "Wine Game")


class TestSortSensitiveColumns(TestCase):
    def test_name_sort_watches_name_columns(self):
        self.assertEqual(game_sort.get_sort_sensitive_columns("name"), {COL_NAME, COL_SORTNAME})

    def test_obsolete_sort_has_no_columns(self):
        self.assertEqual(game_sort.get_sort_sensitive_columns("bogus"), set())


class TestApplyViewSort(TestCase):
    def test_name_sort_is_natural(self):
        games = [
            {"name": "Game 10", "installed": True},
            {"name": "Game 2", "installed": True},
        ]
        result = game_sort.apply_view_sort(games, "name")
        self.assertEqual([game["name"] for game in result], ["Game 2", "Game 10"])

    def test_name_sort_can_be_reversed(self):
        games = [
            {"name": "Alpha", "installed": True},
            {"name": "Beta", "installed": True},
        ]
        result = game_sort.apply_view_sort(games, "name", view_reverse_order=True)
        self.assertEqual([game["name"] for game in result], ["Beta", "Alpha"])

    def test_installed_games_sort_first_in_both_directions(self):
        games = [
            {"name": "Zeta", "year": "1990", "installed": False},
            {"name": "Alpha", "year": "2020", "installed": True},
        ]
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                result = game_sort.apply_view_sort(
                    games, "year", view_reverse_order=reverse, view_sorting_installed_first=True
                )
                self.assertTrue(result[0]["installed"])

    def test_missing_year_falls_back_to_the_service(self):
        games = [{"name": "No Year", "installed": True}]
        result = game_sort.apply_view_sort(games, "year", service=FakeService())
        self.assertEqual([game["name"] for game in result], ["No Year"])
