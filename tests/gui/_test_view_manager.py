from unittest import TestCase
from unittest.mock import MagicMock, patch

from lutris.gui.view_state import GameViewState
from lutris.gui.window import view_manager
from lutris.gui.window.view_manager import GameViewManager
from lutris.util.jobs import IdleTask


class FakeStore:
    """A stand-in for a GameStore, carrying just the game ids the view can resolve."""

    def __init__(self, game_ids):
        self.game_ids = list(game_ids)


class FakeView:
    """A stand-in for a game view; paths are game ids, which keeps the test readable."""

    def __init__(self, game_ids):
        self.game_ids = list(game_ids)
        self.service = None
        self.game_store = None
        self.selected_paths = []

    def get_selected(self):
        return list(self.selected_paths)

    def get_game_id_for_path(self, path):
        return path

    def get_path_for_game_id(self, game_id):
        return game_id if game_id in self.game_ids else None

    def set_game_store(self, game_store):
        self.game_store = game_store
        self.game_ids = list(game_store.game_ids)

    def set_selected(self, paths, scroll_into_view=False):
        self.selected_paths = list(paths)


class FakeHost:
    def __init__(self):
        self.service = None
        self.view_state = GameViewState({})
        self.search_entry = MagicMock()
        self.games_stack = MagicMock()
        self.service_media = MagicMock()
        self.current_view_type = "grid"

    def get_games_from_filters(self):
        return []


class GameViewManagerTestCase(TestCase):
    def setUp(self):
        # The manager owns real GTK objects; replace them so the tests need no display.
        self.gtk_patch = patch.object(view_manager, "Gtk", MagicMock())
        self.store_patch = patch.object(view_manager, "GameStore", MagicMock())
        self.gtk_patch.start()
        self.store_patch.start()
        self.addCleanup(self.gtk_patch.stop)
        self.addCleanup(self.store_patch.stop)
        self.host = FakeHost()
        self.manager = GameViewManager(self.host)


class TestApplyGameStore(GameViewManagerTestCase):
    def test_selection_is_dropped_for_games_no_longer_shown(self):
        view = FakeView(["a", "b"])
        view.selected_paths = ["a", "b"]
        self.manager.views["grid"] = view
        self.host.current_view_type = "grid"

        new_store = FakeStore(["a"])
        self.manager._apply_game_store(new_store, [{"id": "a"}])

        # 'b' is gone from the rebuilt view, so it must not stay selected.
        self.assertEqual(view.selected_paths, ["a"])
        self.assertIs(self.manager.game_store, new_store)
        self.assertIs(self.manager.current_view, view)

    def test_selection_is_kept_when_games_remain(self):
        view = FakeView(["a", "b"])
        view.selected_paths = ["a"]
        self.manager.views["grid"] = view
        self.host.current_view_type = "grid"

        self.manager._apply_game_store(FakeStore(["a", "b"]), [{"id": "a"}, {"id": "b"}])
        self.assertEqual(view.selected_paths, ["a"])

    def test_same_store_is_not_reapplied(self):
        self.manager.views["grid"] = FakeView(["a"])
        self.host.current_view_type = "grid"
        store = self.manager.game_store
        self.manager._apply_game_store(store, [{"id": "a"}])
        self.assertIs(self.manager.game_store, store)


class TestScheduleUpdateStore(GameViewManagerTestCase):
    def _fake_schedule(self, function, *args, **kwargs):
        task = IdleTask()
        task.connect(99)
        return task

    def test_bursts_are_coalesced_into_one_update(self):
        with patch.object(view_manager, "schedule_at_idle", side_effect=self._fake_schedule) as schedule:
            self.manager.schedule_update_store()
            self.manager.schedule_update_store()
            self.manager.schedule_update_store()
        self.assertEqual(schedule.call_count, 1)

    def test_a_new_update_is_scheduled_after_the_last_one_runs(self):
        with patch.object(view_manager, "schedule_at_idle", side_effect=self._fake_schedule) as schedule:
            self.manager.schedule_update_store()
            self.manager._pending_update.disconnect()  # pretend the idle task ran
            self.manager.schedule_update_store()
        self.assertEqual(schedule.call_count, 2)
