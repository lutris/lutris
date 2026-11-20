"""Tests for running GOG cloud syncs with lutris.services.gog_cloud_operation.

These tests verify the operation that publishes a GOG cloud sync's progress for
polling, including cancellation via the stop button, and the order in which
start_cloud_sync() runs a game's syncs.
"""

import unittest
from unittest.mock import MagicMock

import pytest

from lutris.util.test_config import setup_test_environment

setup_test_environment()

from lutris.services import gog_cloud_operation
from lutris.services.gog_cloud import SyncResult
from lutris.services.gog_cloud_operation import (
    CLOUD_SYNC_ENDED,
    CLOUD_SYNC_STARTED,
    CloudSyncCancelled,
    CloudSyncOperation,
    is_cloud_sync_running,
    start_cloud_sync,
)
from lutris.util.notifications import NotificationRegistration, NotificationSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(name: str = "Test Game", service: str = "gog", appid: str = "1234") -> MagicMock:
    game = MagicMock()
    game.id = "1"
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


class TestCloudSyncOperationInit(unittest.TestCase):
    """Test adapter construction."""

    def test_initial_state_pre_launch(self):
        game = _make_game()
        sync_func = MagicMock()
        adapter = CloudSyncOperation(game, sync_func, "pre-launch")
        self.assertEqual(adapter.results, [])
        self.assertFalse(adapter._finished)
        self.assertFalse(adapter._cancelled)
        self.assertIsNone(adapter._error)

    def test_initial_state_post_exit(self):
        game = _make_game()
        sync_func = MagicMock()
        adapter = CloudSyncOperation(game, sync_func, "post-exit")
        self.assertEqual(adapter.direction, "post-exit")
        self.assertIn(game.name, adapter._label)


class TestCloudSyncOperationProgress(unittest.TestCase):
    """Test progress reporting."""

    def _make_adapter(self):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        return CloudSyncOperation(game, sync_func, "pre-launch")

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


class TestCloudSyncOperationCancel(unittest.TestCase):
    """Test cancellation via the stop button."""

    def _make_adapter(self):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        return CloudSyncOperation(game, sync_func, "pre-launch")

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

        def fake_sync(g, cb, resolve_conflict):
            cb(0, 3, "file1.dat")
            # Simulate cancel happening between callbacks
            raise CloudSyncCancelled()

        adapter = CloudSyncOperation(game, fake_sync, "pre-launch")
        result = adapter.run()

        self.assertEqual(result, [])
        self.assertTrue(adapter._finished)
        self.assertIsNone(adapter._error)


class TestCloudSyncOperationRun(unittest.TestCase):
    """Test the run method."""

    def test_run_calls_sync_func(self):
        game = _make_game()
        expected = [_make_sync_result(downloaded=["x"])]
        sync_func = MagicMock(return_value=expected)
        resolve_conflict = MagicMock()
        adapter = CloudSyncOperation(game, sync_func, "pre-launch", resolve_conflict)

        result = adapter.run()

        self.assertEqual(result, expected)
        self.assertEqual(adapter.results, expected)
        sync_func.assert_called_once_with(game, adapter.progress_callback, resolve_conflict)
        self.assertTrue(adapter._finished)

    def test_run_sets_error_on_exception(self):
        game = _make_game()
        sync_func = MagicMock(side_effect=RuntimeError("boom"))
        adapter = CloudSyncOperation(game, sync_func, "pre-launch")

        with self.assertRaises(RuntimeError):
            adapter.run()

        self.assertTrue(adapter._finished)
        self.assertEqual(adapter._error, "boom")

    def test_run_sets_finished_even_on_error(self):
        game = _make_game()
        sync_func = MagicMock(side_effect=ValueError("bad"))
        adapter = CloudSyncOperation(game, sync_func, "post-exit")

        with self.assertRaises(ValueError):
            adapter.run()

        self.assertTrue(adapter._finished)
        progress = adapter.get_progress()
        self.assertTrue(progress.has_ended)


# ---------------------------------------------------------------------------
# start_cloud_sync
# ---------------------------------------------------------------------------


class FakeAsyncCall:
    """Records the syncs start_cloud_sync() puts on a worker thread, to finish by hand."""

    calls: list["FakeAsyncCall"] = []

    def __init__(self, func, callback):
        self.func = func
        self.callback = callback
        FakeAsyncCall.calls.append(self)

    def finish(self, error: BaseException | None = None) -> None:
        self.callback(None, error)


@pytest.fixture
def worker_threads(fake_main_loop, monkeypatch):
    FakeAsyncCall.calls = []
    monkeypatch.setattr(gog_cloud_operation, "AsyncCall", FakeAsyncCall)
    monkeypatch.setattr(gog_cloud_operation, "_operations", {})
    return FakeAsyncCall.calls


def _record(notification: NotificationSource) -> tuple[list[CloudSyncOperation], NotificationRegistration]:
    received: list[CloudSyncOperation] = []
    registration = notification.register(received.append)
    return received, registration


def test_sync_runs_and_reports_its_end(worker_threads, fake_main_loop):
    game = _make_game()
    started, started_registration = _record(CLOUD_SYNC_STARTED)
    ended, ended_registration = _record(CLOUD_SYNC_ENDED)
    done = MagicMock()

    try:
        assert start_cloud_sync(game, "pre-launch", on_done=done)
        fake_main_loop.run_pending()
        assert [operation.direction for operation in started] == ["pre-launch"]
        assert is_cloud_sync_running()

        worker_threads[0].finish(RuntimeError("Even a failed sync ends"))
        fake_main_loop.run_pending()
    finally:
        started_registration.unregister()
        ended_registration.unregister()

    done.assert_called_once_with()
    assert ended == started
    assert not is_cloud_sync_running()


def test_pre_launch_sync_waits_for_the_upload_after_the_last_session(worker_threads, fake_main_loop):
    game = _make_game()
    done = MagicMock()

    start_cloud_sync(game, "post-exit")
    start_cloud_sync(game, "pre-launch", on_done=done)
    assert len(worker_threads) == 1  # Only the upload runs

    worker_threads[0].finish()
    fake_main_loop.run_pending()
    assert len(worker_threads) == 2  # Then the download

    worker_threads[1].finish()
    fake_main_loop.run_pending()
    done.assert_called_once_with()


def test_the_same_sync_does_not_run_twice(worker_threads):
    game = _make_game()

    assert start_cloud_sync(game, "post-exit")
    assert not start_cloud_sync(game, "post-exit")
    assert len(worker_threads) == 1


if __name__ == "__main__":
    unittest.main()
