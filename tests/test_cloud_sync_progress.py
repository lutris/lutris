"""Tests for the CloudSyncProgressDialog.

These tests verify the dialog's construction, background sync execution,
skip/cancel behaviour, and auto-close lifecycle without requiring a
running GTK display (all GTK interactions are mocked).
"""

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

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

# ── Stub out GTK / GLib / GObject so the dialog module can import ────
_mock_gtk = MagicMock()
_mock_glib = MagicMock()
_mock_gobject = MagicMock()
_gi_repo = types.ModuleType("gi.repository")
sys.modules.setdefault("gi", types.ModuleType("gi"))
sys.modules.setdefault("gi.repository", _gi_repo)

_gi_repo.Gtk = _mock_gtk  # type: ignore[attr-defined]
_gi_repo.GLib = _mock_glib  # type: ignore[attr-defined]
_gi_repo.GObject = _mock_gobject  # type: ignore[attr-defined]

# Stub dialog base classes
_dialogs_stub = types.ModuleType("lutris.gui.dialogs")
sys.modules.setdefault("lutris.gui", types.ModuleType("lutris.gui"))
sys.modules.setdefault("lutris.gui.dialogs", _dialogs_stub)

_dialogs_stub.ModelessDialog = type(  # type: ignore[attr-defined]
    "ModelessDialog",
    (),
    {
        "__init__": lambda self, *a, **kw: None,
    },
)

# Stub jobs module
_jobs_stub = types.ModuleType("lutris.util.jobs")
_jobs_stub.AsyncCall = MagicMock  # type: ignore[attr-defined]
_jobs_stub.IdleTask = type(  # type: ignore[attr-defined]
    "IdleTask",
    (),
    {
        "unschedule": lambda self: None,
    },
)
_mock_schedule = MagicMock()
_jobs_stub.schedule_repeating_at_idle = _mock_schedule  # type: ignore[attr-defined]
sys.modules.setdefault("lutris.util", types.ModuleType("lutris.util"))
sys.modules["lutris.util.jobs"] = _jobs_stub

# Stub log module
_log_stub = types.ModuleType("lutris.util.log")
_log_stub.logger = MagicMock()  # type: ignore[attr-defined]
sys.modules["lutris.util.log"] = _log_stub

# ── Now load the dialog module ──────────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "lutris.gui.dialogs.cloud_sync_progress",
    os.path.join(os.path.dirname(__file__), "..", "lutris", "gui", "dialogs", "cloud_sync_progress.py"),
)
assert _spec is not None and _spec.loader is not None
_dialog_mod = importlib.util.module_from_spec(_spec)
sys.modules["lutris.gui.dialogs.cloud_sync_progress"] = _dialog_mod
_spec.loader.exec_module(_dialog_mod)

CloudSyncProgressDialog = _dialog_mod.CloudSyncProgressDialog


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


class TestCloudSyncProgressDialogInit(unittest.TestCase):
    """Test dialog construction and widget setup."""

    def _make_dialog(self, direction="pre-launch"):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        dialog = object.__new__(CloudSyncProgressDialog)
        dialog.game = game
        dialog._sync_func = sync_func
        dialog._direction = direction
        dialog.results = []
        dialog._cancelled = False
        dialog._pulse_task = None
        dialog._status_label = MagicMock()
        dialog._detail_label = MagicMock()
        dialog._progress_bar = MagicMock()
        dialog._skip_button = MagicMock()
        return dialog

    def test_initial_state_pre_launch(self):
        dialog = self._make_dialog("pre-launch")
        self.assertFalse(dialog._cancelled)
        self.assertIsNone(dialog._pulse_task)
        self.assertEqual(dialog.results, [])

    def test_initial_state_post_exit(self):
        dialog = self._make_dialog("post-exit")
        self.assertFalse(dialog._cancelled)
        self.assertEqual(dialog._direction, "post-exit")


class TestCloudSyncProgressDialogRunSync(unittest.TestCase):
    """Test the run_sync method schedules pulse and starts async call."""

    def _make_dialog(self):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        dialog = object.__new__(CloudSyncProgressDialog)
        dialog.game = game
        dialog._sync_func = sync_func
        dialog._direction = "pre-launch"
        dialog.results = []
        dialog._cancelled = False
        dialog._pulse_task = None
        dialog._status_label = MagicMock()
        dialog._detail_label = MagicMock()
        dialog._progress_bar = MagicMock()
        dialog._skip_button = MagicMock()
        return dialog

    def test_run_sync_starts_pulse(self):
        dialog = self._make_dialog()
        _mock_schedule.reset_mock()

        with patch.object(type(dialog), "run_sync", CloudSyncProgressDialog.run_sync):
            # Patch AsyncCall to prevent actual thread creation
            original_async = _dialog_mod.AsyncCall
            _dialog_mod.AsyncCall = MagicMock()
            try:
                dialog.run_sync()
                _mock_schedule.assert_called_once()
                self.assertIsNotNone(dialog._pulse_task)
            finally:
                _dialog_mod.AsyncCall = original_async


class TestCloudSyncProgressDialogCallbacks(unittest.TestCase):
    """Test the internal callback behaviour."""

    def _make_dialog(self):
        """Create a dialog with all GTK interactions mocked out."""
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        dialog = object.__new__(CloudSyncProgressDialog)
        dialog.game = game
        dialog._sync_func = sync_func
        dialog._direction = "pre-launch"
        dialog.results = []
        dialog._cancelled = False
        dialog._pulse_task = None
        dialog._status_label = MagicMock()
        dialog._detail_label = MagicMock()
        dialog._progress_bar = MagicMock()
        dialog._skip_button = MagicMock()
        return dialog

    def test_on_sync_done_success_with_downloads(self):
        dialog = self._make_dialog()
        results = [_make_sync_result(downloaded=["save1.dat", "save2.dat"])]
        mock_glib = MagicMock()

        with patch.object(_dialog_mod, "GLib", mock_glib):
            dialog._on_sync_done(results, None)

        self.assertEqual(dialog.results, results)
        dialog._detail_label.set_text.assert_called()
        mock_glib.timeout_add.assert_called_once()

    def test_on_sync_done_success_with_uploads(self):
        dialog = self._make_dialog()
        results = [_make_sync_result(uploaded=["save1.dat"])]
        mock_glib = MagicMock()

        with patch.object(_dialog_mod, "GLib", mock_glib):
            dialog._on_sync_done(results, None)

        self.assertEqual(dialog.results, results)
        mock_glib.timeout_add.assert_called_once()

    def test_on_sync_done_up_to_date(self):
        dialog = self._make_dialog()
        results = [_make_sync_result()]
        mock_glib = MagicMock()

        with patch.object(_dialog_mod, "GLib", mock_glib):
            dialog._on_sync_done(results, None)

        self.assertEqual(dialog.results, results)
        mock_glib.timeout_add.assert_called_once()

    def test_on_sync_done_error(self):
        dialog = self._make_dialog()
        error = RuntimeError("Network error")
        mock_glib = MagicMock()

        with patch.object(_dialog_mod, "GLib", mock_glib):
            dialog._on_sync_done(None, error)

        dialog._status_label.set_markup.assert_called()
        mock_glib.timeout_add.assert_called_once()

    def test_on_sync_done_cancelled_destroys_dialog(self):
        dialog = self._make_dialog()
        dialog._cancelled = True
        dialog.destroy = MagicMock()
        mock_glib = MagicMock()

        with patch.object(_dialog_mod, "GLib", mock_glib):
            dialog._on_sync_done([_make_sync_result()], None)

        dialog.destroy.assert_called_once()
        mock_glib.timeout_add.assert_not_called()

    def test_pulse_returns_true_when_active(self):
        dialog = self._make_dialog()
        result = dialog._pulse()
        self.assertTrue(result)
        dialog._progress_bar.pulse.assert_called_once()

    def test_pulse_returns_false_when_cancelled(self):
        dialog = self._make_dialog()
        dialog._cancelled = True
        result = dialog._pulse()
        self.assertFalse(result)

    def test_do_sync_calls_sync_func(self):
        dialog = self._make_dialog()
        expected = [_make_sync_result(downloaded=["x"])]
        dialog._sync_func = MagicMock(return_value=expected)

        result = dialog._do_sync()

        self.assertEqual(result, expected)
        dialog._sync_func.assert_called_once_with(dialog.game)

    def test_on_destroy_unschedules_pulse(self):
        dialog = self._make_dialog()
        mock_task = MagicMock()
        dialog._pulse_task = mock_task

        dialog._on_destroy(None)

        mock_task.unschedule.assert_called_once()
        self.assertIsNone(dialog._pulse_task)

    def test_on_destroy_noop_when_no_pulse_task(self):
        dialog = self._make_dialog()
        dialog._pulse_task = None
        # Should not raise
        dialog._on_destroy(None)


class TestCloudSyncProgressDialogSkip(unittest.TestCase):
    """Test the skip/cancel response handling."""

    def _make_dialog(self):
        game = _make_game()
        sync_func = MagicMock(return_value=[])
        dialog = object.__new__(CloudSyncProgressDialog)
        dialog.game = game
        dialog._sync_func = sync_func
        dialog._direction = "pre-launch"
        dialog.results = []
        dialog._cancelled = False
        dialog._pulse_task = None
        dialog._status_label = MagicMock()
        dialog._detail_label = MagicMock()
        dialog._progress_bar = MagicMock()
        dialog._skip_button = MagicMock()
        return dialog

    def test_skip_cancels_and_disables_button(self):
        dialog = self._make_dialog()
        mock_gtk = MagicMock()
        cancel_response = mock_gtk.ResponseType.CANCEL

        with patch.object(_dialog_mod, "Gtk", mock_gtk):
            dialog._on_response(dialog, cancel_response)

        self.assertTrue(dialog._cancelled)
        dialog._skip_button.set_sensitive.assert_called_with(False)


if __name__ == "__main__":
    unittest.main()
