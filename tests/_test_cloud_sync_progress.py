"""Tests for the CloudSyncProgressAdapter.

These tests verify the adapter that bridges GOG cloud sync progress
to the sidebar ProgressBox polling mechanism, including cancellation
via the stop button.
"""

import unittest
from unittest.mock import MagicMock

from lutris.util.test_config import setup_test_environment

setup_test_environment()

from lutris.gui.dialogs.cloud_sync_progress import CloudSyncCancelled, CloudSyncProgressAdapter
from lutris.gui.widgets.progress_box import ProgressInfo  # noqa: F401
from lutris.services.gog_cloud import SyncResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(name: str = "Test Game", service: str = "gog", appid: str = "1234") -> MagicMock:
    game = MagicMock()
    game.name = name
    game.service = service
    game.appid = appid
    return game


def _make_sync_result(downloaded=None, uploaded=None, error=None) -> SyncResult:
    r = SyncResult()
    r.downloaded = list(downloaded or [])
    r.uploaded = list(uploaded or [])
    r.error = error
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCloudSyncProgressAdapterInit(unittest.TestCase):
    """Test adapter construction."""

    def test_initial_state_pre_launch(self):
        game = _make_game()
        sync_func = MagicMock()
        adapter = CloudSyncProgressAdapter(game, sync_func, "pre-launch")
        self.assertEqual(adapter.results, [])
        self.assertFalse(adapter._finished)
        self.assertFalse(adapter._cancelled)
        self.assertIsNone(adapter._error)

    def test_initial_state_post_exit(self):
        game = _make_game()
        sync_func = MagicMock()
        adapter = CloudSyncProgressAdapter(game, sync_func, "post-exit")
        self.assertEqual(adapter._direction, "post-exit")
        self.assertIn(game.name, adapter._label)


class TestCloudSyncProgressAdapterProgress(unittest.TestCase):
    """Test progress reporting."""

    def _make_adapter(self):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        return CloudSyncProgressAdapter(game, sync_func, "pre-launch")

    def test_initial_progress_is_zero(self):
        adapter = self._make_adapter()
        progress = adapter.get_progress()
        self.assertEqual(progress.progress, 0.0)
        self.assertFalse(progress.has_ended)

    def test_progress_callback_updates_state(self):
        adapter = self._make_adapter()
        adapter.progress_callback(2, 5, "save.dat")
        progress = adapter.get_progress()
        self.assertAlmostEqual(progress.progress, 3 / 5)
        self.assertIn("save.dat", progress.label_markup)

    def test_finished_progress_reports_ended(self):
        adapter = self._make_adapter()
        adapter._finished = True
        progress = adapter.get_progress()
        self.assertTrue(progress.has_ended)

    def test_error_progress_reports_ended_with_error(self):
        adapter = self._make_adapter()
        adapter._finished = True
        adapter._error = "Network error"
        progress = adapter.get_progress()
        self.assertTrue(progress.has_ended)
        self.assertIn("Network error", progress.label_markup)

    def test_progress_provides_stop_function(self):
        adapter = self._make_adapter()
        progress = adapter.get_progress()
        self.assertTrue(progress.can_stop)
        self.assertEqual(progress.stop_function, adapter.cancel)

    def test_progress_hides_stop_after_cancel(self):
        adapter = self._make_adapter()
        adapter.cancel()
        progress = adapter.get_progress()
        self.assertFalse(progress.can_stop)


class TestCloudSyncProgressAdapterCancel(unittest.TestCase):
    """Test cancellation via the stop button."""

    def _make_adapter(self):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        return CloudSyncProgressAdapter(game, sync_func, "pre-launch")

    def test_cancel_sets_flag(self):
        adapter = self._make_adapter()
        adapter.cancel()
        self.assertTrue(adapter._cancelled)

    def test_progress_callback_raises_when_cancelled(self):
        adapter = self._make_adapter()
        adapter.cancel()
        with self.assertRaises(CloudSyncCancelled):
            adapter.progress_callback(0, 5, "save.dat")

    def test_run_handles_cancellation_gracefully(self):
        game = _make_game()

        def fake_sync(g, cb):
            cb(0, 3, "file1.dat")
            # Simulate cancel happening between callbacks
            raise CloudSyncCancelled()

        adapter = CloudSyncProgressAdapter(game, fake_sync, "pre-launch")
        result = adapter.run()

        self.assertEqual(result, [])
        self.assertTrue(adapter._finished)
        self.assertIsNone(adapter._error)


class TestCloudSyncProgressAdapterRun(unittest.TestCase):
    """Test the run method."""

    def test_run_calls_sync_func(self):
        game = _make_game()
        expected = [_make_sync_result(downloaded=["x"])]
        sync_func = MagicMock(return_value=expected)
        adapter = CloudSyncProgressAdapter(game, sync_func, "pre-launch")

        result = adapter.run()

        self.assertEqual(result, expected)
        self.assertEqual(adapter.results, expected)
        sync_func.assert_called_once_with(game, adapter.progress_callback)
        self.assertTrue(adapter._finished)

    def test_run_sets_error_on_exception(self):
        game = _make_game()
        sync_func = MagicMock(side_effect=RuntimeError("boom"))
        adapter = CloudSyncProgressAdapter(game, sync_func, "pre-launch")

        with self.assertRaises(RuntimeError):
            adapter.run()

        self.assertTrue(adapter._finished)
        self.assertEqual(adapter._error, "boom")

    def test_run_sets_finished_even_on_error(self):
        game = _make_game()
        sync_func = MagicMock(side_effect=ValueError("bad"))
        adapter = CloudSyncProgressAdapter(game, sync_func, "post-exit")

        with self.assertRaises(ValueError):
            adapter.run()

        self.assertTrue(adapter._finished)
        progress = adapter.get_progress()
        self.assertTrue(progress.has_ended)


if __name__ == "__main__":
    unittest.main()
