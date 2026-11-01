from unittest import TestCase

from lutris.gui.game_filter import (
    EmptyViewReason,
    FilterValues,
    SidebarSelection,
    build_search,
    filter_games,
    get_empty_view_message,
    get_empty_view_reason,
    get_sql_filters,
    is_game_displayed,
)
from lutris.search import GameSearch

GAMES = [
    {"id": 1, "name": "Installed A", "installed": True},
    {"id": 2, "name": "Not installed B", "installed": False},
]


def empty_search() -> GameSearch:
    return GameSearch("", service=None)


class TestEmptyViewReason(TestCase):
    def test_empty_view_defaults_to_splash(self):
        self.assertEqual(get_empty_view_reason(FilterValues({}), False), EmptyViewReason.SPLASH)

    def test_installed_filter_with_uninstalled_games(self):
        values = FilterValues({"installed": True})
        self.assertEqual(get_empty_view_reason(values, True), EmptyViewReason.NO_INSTALLED_GAMES)
        self.assertEqual(get_empty_view_reason(values, False), EmptyViewReason.SPLASH)

    def test_favorite_and_hidden_categories(self):
        self.assertEqual(
            get_empty_view_reason(FilterValues({"category": "favorite"}), False), EmptyViewReason.NO_FAVORITES
        )
        self.assertEqual(
            get_empty_view_reason(FilterValues({"category": ".hidden"}), False), EmptyViewReason.NO_HIDDEN_GAMES
        )

    def test_other_filter_reports_no_games(self):
        self.assertEqual(get_empty_view_reason(FilterValues({"runner": "wine"}), False), EmptyViewReason.NO_GAMES)

    def test_text_reasons(self):
        self.assertEqual(
            get_empty_view_reason(FilterValues({"text": "mario"}), False), EmptyViewReason.NO_GAMES_MATCHING_TEXT
        )
        self.assertEqual(
            get_empty_view_reason(FilterValues({"text": "mario", "category": "favorite"}), False),
            EmptyViewReason.NO_FAVORITES_MATCHING_TEXT,
        )
        self.assertEqual(
            get_empty_view_reason(FilterValues({"text": "mario", "category": ".hidden"}), False),
            EmptyViewReason.NO_HIDDEN_MATCHING_TEXT,
        )
        self.assertEqual(
            get_empty_view_reason(FilterValues({"text": "mario", "installed": True}), True),
            EmptyViewReason.NO_INSTALLED_MATCHING_TEXT,
        )


class TestEmptyViewMessage(TestCase):
    def test_splash_has_no_label(self):
        self.assertIsNone(get_empty_view_message(FilterValues({}), False))

    def test_generic_message(self):
        self.assertEqual(get_empty_view_message(FilterValues({"runner": "wine"}), False), "No games found")

    def test_text_message_includes_search(self):
        message = get_empty_view_message(FilterValues({"text": "mario"}), False)
        self.assertIn("mario", message)


class TestBuildSearchAndFilterGames(TestCase):
    def test_installed_filter_keeps_only_installed_games(self):
        # Category '.hidden' avoids the hidden predicate so the test touches no database.
        values = FilterValues({"installed": True, "category": ".hidden"})
        searches = [build_search(empty_search(), values)]
        result = filter_games(GAMES, searches)
        self.assertEqual([game["id"] for game in result], [1])

    def test_empty_searches_leave_games_alone(self):
        self.assertEqual(filter_games(GAMES, [empty_search()]), GAMES)

    def test_all_searches_must_match(self):
        values = FilterValues({"category": ".hidden"})
        installed = build_search(empty_search(), FilterValues({"installed": True, "category": ".hidden"}))
        result = filter_games(GAMES, [build_search(empty_search(), values), installed])
        self.assertEqual([game["id"] for game in result], [1])


class TestGetSqlFilters(TestCase):
    def test_runner_and_platform_are_pushed_to_sql(self):
        values = FilterValues({"runner": "wine", "platform": "Linux"})
        self.assertEqual(get_sql_filters(values, empty_search()), {"runner": "wine", "platform": "Linux"})

    def test_installed_is_pushed_to_sql(self):
        values = FilterValues({"installed": True})
        self.assertEqual(get_sql_filters(values, empty_search()), {"installed": "1"})

    def test_text_is_not_pushed_to_sql(self):
        values = FilterValues({"text": "mario"})
        self.assertEqual(get_sql_filters(values, empty_search()), {})


class TestIsGameDisplayed(TestCase):
    def test_no_selection_displays_everything(self):
        self.assertTrue(is_game_displayed(None, [], is_stopped=True, enforce_hidden=True))

    def test_stopped_game_leaves_running_page(self):
        selection = SidebarSelection("dynamic_category", "running")
        self.assertFalse(is_game_displayed(selection, [], is_stopped=True, enforce_hidden=True))
        self.assertTrue(is_game_displayed(selection, [], is_stopped=False, enforce_hidden=True))

    def test_hidden_game_leaves_recent_and_missing_pages(self):
        selection = SidebarSelection("dynamic_category", "recent")
        self.assertFalse(is_game_displayed(selection, [".hidden"], is_stopped=False, enforce_hidden=True))
        self.assertTrue(is_game_displayed(selection, [".hidden"], is_stopped=False, enforce_hidden=False))

    def test_category_membership_is_enforced(self):
        selection = SidebarSelection("category", "shooters")
        self.assertTrue(is_game_displayed(selection, ["shooters"], is_stopped=False, enforce_hidden=True))
        self.assertFalse(is_game_displayed(selection, ["rpg"], is_stopped=False, enforce_hidden=True))

    def test_hidden_games_leave_a_normal_category(self):
        selection = SidebarSelection("category", "shooters")
        self.assertFalse(is_game_displayed(selection, ["shooters", ".hidden"], is_stopped=False, enforce_hidden=True))

    def test_hidden_page_keeps_hidden_games(self):
        selection = SidebarSelection("category", ".hidden")
        self.assertTrue(is_game_displayed(selection, [".hidden"], is_stopped=False, enforce_hidden=True))
