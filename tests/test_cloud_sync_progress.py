"""Tests for the CloudSyncProgressAdapter.

These tests verify the adapter that bridges GOG cloud sync progress
to the sidebar ProgressBox polling mechanism, including cancellation
via the stop button.
"""

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# ── Load gog_cloud first (no GTK dependency) ────────────────────────
_cloud_spec = importlib.util.spec_from_file_location(
    "lutris.services.gog_cloud",
    os.path.join(os.path.dirname(__file__), "..", "lutris", "services", "gog_cloud.py"),
)
assert _cloud_spec is not None and _cloud_spec.loader is not None
_cloud_mod = importlib.util.module_from_spec(_cloud_spec)
sys.modules["lutris.services.gog_cloud"] = _cloud_mod
_cloud_spec.loader.exec_module(_cloud_mod)

SyncResult = _cloud_mod.SyncResult

# ── Stub lutris.services package to prevent __init__.py / GTK chain ─
if "lutris.services" not in sys.modules:
    _services_stub = types.ModuleType("lutris.services")
    sys.modules["lutris.services"] = _services_stub
sys.modules["lutris.services"].gog_cloud = _cloud_mod  # type: ignore[attr-defined]

# ── Stub out GTK / GLib / GObject so the module can import ────
_mock_gtk = MagicMock()
_mock_glib = MagicMock()
_mock_gobject = MagicMock()
_gi_repo = types.ModuleType("gi.repository")
sys.modules.setdefault("gi", types.ModuleType("gi"))
sys.modules.setdefault("gi.repository", _gi_repo)

_gi_repo.Gtk = _mock_gtk  # type: ignore[attr-defined]
_gi_repo.GLib = _mock_glib  # type: ignore[attr-defined]
_gi_repo.GObject = _mock_gobject  # type: ignore[attr-defined]

# Stub GUI modules
_dialogs_stub = types.ModuleType("lutris.gui.dialogs")
sys.modules.setdefault("lutris.gui", types.ModuleType("lutris.gui"))
sys.modules.setdefault("lutris.gui.dialogs", _dialogs_stub)
sys.modules.setdefault("lutris.gui.widgets", types.ModuleType("lutris.gui.widgets"))

# Stub jobs module
_jobs_stub = types.ModuleType("lutris.util.jobs")
_jobs_stub.AsyncCall = MagicMock  # type: ignore[attr-defined]
_jobs_stub.schedule_repeating_at_idle = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("lutris.util", types.ModuleType("lutris.util"))
sys.modules["lutris.util.jobs"] = _jobs_stub

# Stub log module
_log_stub = types.ModuleType("lutris.util.log")
_log_stub.logger = MagicMock()  # type: ignore[attr-defined]
sys.modules["lutris.util.log"] = _log_stub

# ── Now load the progress_box and adapter modules ──────────────────
_pb_spec = importlib.util.spec_from_file_location(
    "lutris.gui.widgets.progress_box",
    os.path.join(os.path.dirname(__file__), "..", "lutris", "gui", "widgets", "progress_box.py"),
)
assert _pb_spec is not None and _pb_spec.loader is not None
_pb_mod = importlib.util.module_from_spec(_pb_spec)
sys.modules["lutris.gui.widgets.progress_box"] = _pb_mod
_pb_spec.loader.exec_module(_pb_mod)

ProgressInfo = _pb_mod.ProgressInfo

_spec = importlib.util.spec_from_file_location(
    "lutris.gui.dialogs.cloud_sync_progress",
    os.path.join(os.path.dirname(__file__), "..", "lutris", "gui", "dialogs", "cloud_sync_progress.py"),
)
assert _spec is not None and _spec.loader is not None
_adapter_mod = importlib.util.module_from_spec(_spec)
sys.modules["lutris.gui.dialogs.cloud_sync_progress"] = _adapter_mod
_spec.loader.exec_module(_adapter_mod)

CloudSyncProgressAdapter = _adapter_mod.CloudSyncProgressAdapter
CloudSyncCancelled = _adapter_mod.CloudSyncCancelled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(name: str = "Test Game", service: str = "gog", appid: str = "1234") -> MagicMock:
    game = MagicMock()
    game.name = name
    game.service = service
    game.appid = appid
    return game


def _make_sync_result(downloaded=None, uploaded=None, error=None) -> "SyncResult":  # type: ignore[valid-type]
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
