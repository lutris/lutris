"""Tests for lutris.services.gog_cloud_hooks

Tests the game lifecycle integration hooks for GOG cloud sync.
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

SyncAction = _cloud_mod.SyncAction
SyncResult = _cloud_mod.SyncResult
CloudSaveLocation = _cloud_mod.CloudSaveLocation

# ── Stub lutris.services package to prevent __init__.py / GTK chain ─
if "lutris.services" not in sys.modules:
    _services_stub = types.ModuleType("lutris.services")
    sys.modules["lutris.services"] = _services_stub
sys.modules["lutris.services"].gog_cloud = _cloud_mod  # type: ignore[attr-defined]

# ── Now load gog_cloud_hooks (its "from lutris.services.gog_cloud"
#    will find the module we already placed in sys.modules) ──────────
_spec = importlib.util.spec_from_file_location(
    "lutris.services.gog_cloud_hooks",
    os.path.join(os.path.dirname(__file__), "..", "lutris", "services", "gog_cloud_hooks.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["lutris.services.gog_cloud_hooks"] = _mod
_spec.loader.exec_module(_mod)

sync_before_launch = _mod.sync_before_launch
sync_after_quit = _mod.sync_after_quit
_get_gog_service = _mod._get_gog_service
_get_game_runner_info = _mod._get_game_runner_info
_resolve_save_locations = _mod._resolve_save_locations


class TestGetGogService(unittest.TestCase):
    """Test the _get_gog_service helper."""

    def test_returns_authenticated_service(self):
        mock_service = MagicMock()
        mock_service.is_authenticated.return_value = True

        mock_gog_mod = MagicMock(GOGService=MagicMock(return_value=mock_service))
        with patch.dict(sys.modules, {"lutris.services.gog": mock_gog_mod}):
            result = _get_gog_service()
        self.assertEqual(result, mock_service)

    def test_returns_none_when_not_authenticated(self):
        mock_service = MagicMock()
        mock_service.is_authenticated.return_value = False

        mock_gog_mod = MagicMock(GOGService=MagicMock(return_value=mock_service))
        with patch.dict(sys.modules, {"lutris.services.gog": mock_gog_mod}):
            result = _get_gog_service()
        self.assertIsNone(result)

    def test_returns_none_on_import_error(self):
        with patch.dict(sys.modules, {"lutris.services.gog": None}):
            result = _get_gog_service()
        self.assertIsNone(result)


class TestGetGameRunnerInfo(unittest.TestCase):
    """Test _get_game_runner_info helper."""

    def test_native_linux_game(self):
        game = MagicMock()
        game.runner_name = "linux"
        game.directory = "/opt/games/mygame"

        info = _get_game_runner_info(game)
        self.assertTrue(info["is_native"])
        self.assertEqual(info["platform"], "linux")
        self.assertIsNone(info["wine_prefix"])
        self.assertEqual(info["install_path"], "/opt/games/mygame")

    def test_wine_game(self):
        game = MagicMock()
        game.runner_name = "wine"
        game.directory = "/opt/games/mygame"
        game.runner.prefix_path = "/home/user/.wine"

        with patch.dict(os.environ, {"USER": "testuser"}):
            info = _get_game_runner_info(game)
        self.assertFalse(info["is_native"])
        self.assertEqual(info["platform"], "windows")
        self.assertEqual(info["wine_prefix"], "/home/user/.wine")
        self.assertEqual(info["wine_user"], "testuser")

    def test_no_runner(self):
        game = MagicMock()
        game.runner_name = ""
        game.runner = None
        game.directory = ""

        info = _get_game_runner_info(game)
        self.assertFalse(info["is_native"])
        self.assertIsNone(info["wine_prefix"])


class TestSyncBeforeLaunch(unittest.TestCase):
    """Test sync_before_launch function."""

    def test_skips_non_gog_game(self):
        game = MagicMock()
        game.service = "steam"
        game.appid = "12345"

        results = sync_before_launch(game)
        self.assertEqual(results, [])

    def test_skips_no_appid(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = None

        results = sync_before_launch(game)
        self.assertEqual(results, [])

    def test_skips_when_no_service(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"

        with patch.object(_mod, "_get_gog_service", return_value=None):
            results = sync_before_launch(game)
        self.assertEqual(results, [])

    def test_skips_when_no_save_locations(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"

        mock_service = MagicMock()
        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=[]),
        ):
            results = sync_before_launch(game)
        self.assertEqual(results, [])

    def test_syncs_download_direction(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"

        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.DOWNLOAD, downloaded=["a.sav"])

        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_before_launch(game)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.DOWNLOAD)
        mock_sync.sync_saves.assert_called_once_with(
            "12345", "/tmp/saves", "saves", "windows", preferred_action="download"
        )


class TestSyncAfterQuit(unittest.TestCase):
    """Test sync_after_quit function."""

    def test_skips_non_gog_game(self):
        game = MagicMock()
        game.service = "egs"
        game.appid = "12345"

        results = sync_after_quit(game)
        self.assertEqual(results, [])

    def test_syncs_upload_direction(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"

        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.UPLOAD, uploaded=["save.dat"])

        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_after_quit(game)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.UPLOAD)
        mock_sync.sync_saves.assert_called_once_with(
            "12345", "/tmp/saves", "saves", "windows", preferred_action="upload"
        )

    def test_handles_multiple_save_locations(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"

        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.NONE)

        save_locations = [
            {"name": "__default", "save_path": "/tmp/default", "platform": "windows"},
            {"name": "saves", "save_path": "/tmp/saves", "platform": "windows"},
        ]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_after_quit(game)

        self.assertEqual(len(results), 2)
        self.assertEqual(mock_sync.sync_saves.call_count, 2)

    def test_handles_sync_error(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"

        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(error="Network error")

        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_after_quit(game)

        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].error)


class TestResolveSaveLocations(unittest.TestCase):
    """Test _resolve_save_locations helper."""

    def test_returns_empty_on_token_error(self):
        game = MagicMock()
        game.appid = "12345"
        game.runner_name = "wine"
        game.directory = "/opt/games/mygame"

        service = MagicMock()
        service.load_token.side_effect = Exception("no token")

        result = _resolve_save_locations(game, service)
        self.assertEqual(result, [])

    def test_returns_empty_on_credentials_error(self):
        game = MagicMock()
        game.appid = "12345"
        game.runner_name = "wine"
        game.directory = "/opt/games/mygame"

        service = MagicMock()
        service.load_token.return_value = {"access_token": "tok", "refresh_token": "ref"}

        with patch.object(_mod, "get_game_client_credentials", side_effect=ValueError("no builds")):
            result = _resolve_save_locations(game, service)
        self.assertEqual(result, [])

    def test_resolves_save_locations(self):
        game = MagicMock()
        game.appid = "12345"
        game.runner_name = "linux"
        game.runner = None
        game.directory = "/opt/games/mygame"

        service = MagicMock()
        service.load_token.return_value = {"access_token": "tok", "refresh_token": "ref"}

        mock_locations = [
            CloudSaveLocation(name="saves", location="<?INSTALL?>/saves"),
        ]

        with (
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(_mod, "get_game_scoped_token", return_value={"access_token": "gtoken", "user_id": "u1"}),
            patch.object(_mod, "get_cloud_save_locations", return_value=mock_locations),
        ):
            result = _resolve_save_locations(game, service)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "saves")
        self.assertEqual(result[0]["save_path"], "/opt/games/mygame/saves")

    def test_returns_empty_on_scoped_token_error(self):
        game = MagicMock()
        game.appid = "12345"
        game.runner_name = "linux"
        game.directory = "/opt/games/mygame"

        service = MagicMock()
        service.load_token.return_value = {"access_token": "tok", "refresh_token": "ref"}

        with (
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(_mod, "get_game_scoped_token", side_effect=ValueError("bad")),
        ):
            result = _resolve_save_locations(game, service)
        self.assertEqual(result, [])

    def test_returns_empty_on_no_access_token(self):
        game = MagicMock()
        game.appid = "12345"
        game.runner_name = "linux"
        game.directory = "/opt/games/mygame"

        service = MagicMock()
        service.load_token.return_value = {"access_token": "tok", "refresh_token": "ref"}

        with (
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(_mod, "get_game_scoped_token", return_value={"access_token": "", "user_id": "u1"}),
        ):
            result = _resolve_save_locations(game, service)
        self.assertEqual(result, [])

    def test_returns_empty_on_no_locations(self):
        game = MagicMock()
        game.appid = "12345"
        game.runner_name = "linux"
        game.runner = None
        game.directory = "/opt/games/mygame"

        service = MagicMock()
        service.load_token.return_value = {"access_token": "tok", "refresh_token": "ref"}

        with (
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(_mod, "get_game_scoped_token", return_value={"access_token": "gtoken", "user_id": "u1"}),
            patch.object(_mod, "get_cloud_save_locations", return_value=[]),
        ):
            result = _resolve_save_locations(game, service)
        self.assertEqual(result, [])


class TestSyncBeforeLaunchBranches(unittest.TestCase):
    """Test sync_before_launch error/conflict branches."""

    def _make_game(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"
        return game

    def test_sync_error_in_result(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(error="Connection refused")
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_before_launch(game)
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].error)

    def test_conflict_dialog_shown_user_downloads(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        # First call returns conflict, second (after dialog) returns download
        mock_sync.sync_saves.side_effect = [
            SyncResult(action=SyncAction.CONFLICT),
            SyncResult(action=SyncAction.DOWNLOAD, downloaded=["a.sav"]),
        ]
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
            patch.object(_mod, "_show_conflict_dialog", return_value="download"),
        ):
            results = sync_before_launch(game)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.DOWNLOAD)
        self.assertEqual(mock_sync.sync_saves.call_count, 2)

    def test_conflict_dialog_user_skips(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.CONFLICT)
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
            patch.object(_mod, "_show_conflict_dialog", return_value=None),
        ):
            results = sync_before_launch(game)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.CONFLICT)
        # Only one call since user skipped
        self.assertEqual(mock_sync.sync_saves.call_count, 1)

    def test_none_result(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.NONE)
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_before_launch(game)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.NONE)


class TestSyncAfterQuitBranches(unittest.TestCase):
    """Test sync_after_quit additional branches."""

    def _make_game(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"
        return game

    def test_skips_when_no_service(self):
        game = self._make_game()
        with patch.object(_mod, "_get_gog_service", return_value=None):
            results = sync_after_quit(game)
        self.assertEqual(results, [])

    def test_skips_when_no_save_locations(self):
        game = self._make_game()
        mock_service = MagicMock()
        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=[]),
        ):
            results = sync_after_quit(game)
        self.assertEqual(results, [])

    def test_conflict_dialog_shown_user_uploads(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.side_effect = [
            SyncResult(action=SyncAction.CONFLICT),
            SyncResult(action=SyncAction.UPLOAD, uploaded=["a.sav"]),
        ]
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
            patch.object(_mod, "_show_conflict_dialog", return_value="upload"),
        ):
            results = sync_after_quit(game)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.UPLOAD)
        self.assertEqual(mock_sync.sync_saves.call_count, 2)

    def test_conflict_dialog_user_skips(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.CONFLICT)
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
            patch.object(_mod, "_show_conflict_dialog", return_value=None),
        ):
            results = sync_after_quit(game)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.CONFLICT)
        self.assertEqual(mock_sync.sync_saves.call_count, 1)

    def test_none_result(self):
        game = self._make_game()
        mock_service = MagicMock()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.NONE)
        save_locations = [{"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}]

        with (
            patch.object(_mod, "_get_gog_service", return_value=mock_service),
            patch.object(_mod, "_resolve_save_locations", return_value=save_locations),
            patch.object(_mod, "GOGCloudSync", return_value=mock_sync),
        ):
            results = sync_after_quit(game)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, SyncAction.NONE)


class TestShowConflictDialog(unittest.TestCase):
    """Test _show_conflict_dialog helper."""

    _show_conflict_dialog = staticmethod(_mod._show_conflict_dialog)

    def test_returns_none_on_import_error(self):
        """When GTK isn't available, should return None gracefully."""
        with patch.dict(sys.modules, {"lutris.gui.dialogs.cloud_sync": None}):
            result = self._show_conflict_dialog("Game", "saves")
        self.assertIsNone(result)

    def test_returns_dialog_action(self):
        """When dialog can be constructed, returns its action."""
        mock_dialog = MagicMock()
        mock_dialog.action = "download"
        mock_dialog_cls = MagicMock(return_value=mock_dialog)
        mock_module = MagicMock(CloudSyncConflictDialog=mock_dialog_cls)

        with patch.dict(sys.modules, {"lutris.gui.dialogs.cloud_sync": mock_module}):
            result = self._show_conflict_dialog("Game", "saves")
        self.assertEqual(result, "download")
        mock_dialog_cls.assert_called_once_with("Game", "saves")


class TestSyncLocation(unittest.TestCase):
    """Test _sync_location helper directly."""

    _sync_location = staticmethod(_mod._sync_location)

    def _make_game(self):
        game = MagicMock()
        game.service = "gog"
        game.appid = "12345"
        game.name = "Test Game"
        return game

    def test_no_conflict_returns_directly(self):
        game = self._make_game()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.DOWNLOAD, downloaded=["x"])
        loc = {"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}

        result = self._sync_location(mock_sync, game, loc, "download", "test")
        self.assertEqual(result.action, SyncAction.DOWNLOAD)
        mock_sync.sync_saves.assert_called_once()

    def test_conflict_retries_with_user_choice(self):
        game = self._make_game()
        mock_sync = MagicMock()
        mock_sync.sync_saves.side_effect = [
            SyncResult(action=SyncAction.CONFLICT),
            SyncResult(action=SyncAction.UPLOAD, uploaded=["y"]),
        ]
        loc = {"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}

        with patch.object(_mod, "_show_conflict_dialog", return_value="upload"):
            result = self._sync_location(mock_sync, game, loc, "download", "test")
        self.assertEqual(result.action, SyncAction.UPLOAD)
        self.assertEqual(mock_sync.sync_saves.call_count, 2)

    def test_conflict_skip_returns_conflict(self):
        game = self._make_game()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(action=SyncAction.CONFLICT)
        loc = {"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}

        with patch.object(_mod, "_show_conflict_dialog", return_value=None):
            result = self._sync_location(mock_sync, game, loc, "download", "test")
        self.assertEqual(result.action, SyncAction.CONFLICT)
        mock_sync.sync_saves.assert_called_once()

    def test_error_result_logged(self):
        game = self._make_game()
        mock_sync = MagicMock()
        mock_sync.sync_saves.return_value = SyncResult(error="failed")
        loc = {"name": "saves", "save_path": "/tmp/saves", "platform": "windows"}

        result = self._sync_location(mock_sync, game, loc, "upload", "test")
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
