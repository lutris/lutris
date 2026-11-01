from unittest import TestCase

from lutris.gui.view_state import GameViewState


class TestGameViewStateValues(TestCase):
    def test_defaults(self):
        values = GameViewState({}).values
        self.assertEqual(values.text, "")
        self.assertFalse(values.installed)
        self.assertEqual(values.category, "all")
        self.assertIsNone(values.dynamic_category)
        self.assertIsNone(values.service)

    def test_set_text_and_installed(self):
        state = GameViewState({})
        state.set_text("mario")
        state.set_installed(True)
        self.assertEqual(state.values.text, "mario")
        self.assertTrue(state.values.installed)


class TestSelectSidebar(TestCase):
    def test_selecting_a_row_replaces_other_filters(self):
        state = GameViewState({"category": "all", "installed": True, "text": "mario"})
        filter_type = state.select_sidebar("service", "gog")
        self.assertEqual(filter_type, "service")
        self.assertEqual(state.filters["service"], "gog")
        for stale in ("category", "dynamic_category", "saved_search", "runner", "platform"):
            self.assertNotIn(stale, state.filters)

    def test_selecting_a_row_keeps_text_and_installed(self):
        state = GameViewState({"category": "all", "installed": True, "text": "mario"})
        state.select_sidebar("service", "gog")
        self.assertEqual(state.filters["text"], "mario")
        self.assertTrue(state.filters["installed"])

    def test_user_category_is_stored_as_category(self):
        state = GameViewState({})
        self.assertEqual(state.select_sidebar("user_category", "shooters"), "category")
        self.assertEqual(state.filters["category"], "shooters")

    def test_dynamic_category_is_stored(self):
        state = GameViewState({})
        state.select_sidebar("dynamic_category", "running")
        self.assertEqual(state.filters["dynamic_category"], "running")


class TestIsSortSensitive(TestCase):
    def test_no_dynamic_category_is_always_sortable(self):
        self.assertTrue(GameViewState({"category": "all"}).is_sort_sensitive({"running"}, set()))

    def test_sortable_dynamic_category(self):
        state = GameViewState({"dynamic_category": "running"})
        self.assertTrue(state.is_sort_sensitive({"running", "recent"}, {"running"}))

    def test_fixed_order_dynamic_category(self):
        state = GameViewState({"dynamic_category": "recent"})
        self.assertFalse(state.is_sort_sensitive({"running", "recent"}, {"running"}))


class TestGetGameSearch(TestCase):
    def test_search_is_cached_until_text_changes(self):
        state = GameViewState({"text": "mario"})
        first = state.get_game_search(None)
        self.assertIs(state.get_game_search(None), first)

        state.set_text("luigi")
        self.assertIsNot(state.get_game_search(None), first)

    def test_search_is_rebuilt_when_service_changes(self):
        class FakeService:
            id = "fake"

        state = GameViewState({"text": "mario"})
        first = state.get_game_search(None)
        self.assertIsNot(state.get_game_search(FakeService()), first)
