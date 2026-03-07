"""Tests for lutris.services.gog_cloud

Tests the GOG cloud save synchronization implementation including:
- Data models (CloudSaveLocation, SyncFile, SyncResult)
- Cloud storage client (GOGCloudStorageClient)
- Sync classifier (SyncClassifier)
- Game client credentials retrieval
- Game-scoped token exchange
- Cloud save location discovery
- Save path resolution
- File listing utilities
- Full sync orchestration (GOGCloudSync)
"""

import gzip
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

# Load gog_cloud directly from file to avoid lutris.services.__init__
# which triggers GTK imports that conflict in test environments.
_spec = importlib.util.spec_from_file_location(
    "lutris.services.gog_cloud",
    os.path.join(os.path.dirname(__file__), "..", "lutris", "services", "gog_cloud.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["lutris.services.gog_cloud"] = _mod
_spec.loader.exec_module(_mod)

EMPTY_GZIP_MD5 = _mod.EMPTY_GZIP_MD5
CloudSaveLocation = _mod.CloudSaveLocation
GOGCloudStorageClient = _mod.GOGCloudStorageClient
GOGCloudSync = _mod.GOGCloudSync
SyncAction = _mod.SyncAction
SyncClassifier = _mod.SyncClassifier
SyncFile = _mod.SyncFile
SyncResult = _mod.SyncResult
create_directory_map = _mod.create_directory_map
get_cloud_save_locations = _mod.get_cloud_save_locations
get_game_client_credentials = _mod.get_game_client_credentials
get_game_scoped_token = _mod.get_game_scoped_token
get_relative_path = _mod.get_relative_path
resolve_save_path = _mod.resolve_save_path

from lutris.util.http import HTTPError


class TestSyncAction(unittest.TestCase):
    """Test the SyncAction enum."""

    def test_values(self):
        self.assertEqual(SyncAction.DOWNLOAD.value, 0)
        self.assertEqual(SyncAction.UPLOAD.value, 1)
        self.assertEqual(SyncAction.CONFLICT.value, 2)
        self.assertEqual(SyncAction.NONE.value, 3)


class TestCloudSaveLocation(unittest.TestCase):
    """Test the CloudSaveLocation dataclass."""

    def test_creation(self):
        loc = CloudSaveLocation(name="__default", location="<?INSTALL?>/saves")
        self.assertEqual(loc.name, "__default")
        self.assertEqual(loc.location, "<?INSTALL?>/saves")


class TestSyncFile(unittest.TestCase):
    """Test the SyncFile dataclass."""

    def test_creation(self):
        f = SyncFile(relative_path="saves/game.sav", absolute_path="/home/user/saves/game.sav")
        self.assertEqual(f.relative_path, "saves/game.sav")
        self.assertEqual(f.absolute_path, "/home/user/saves/game.sav")
        self.assertIsNone(f.md5)
        self.assertIsNone(f.update_time)
        self.assertIsNone(f.update_ts)

    def test_creation_with_metadata(self):
        f = SyncFile(
            relative_path="test.sav",
            absolute_path="/tmp/test.sav",
            md5="abc123",
            update_time="2024-01-01T00:00:00+00:00",
            update_ts=1704067200.0,
        )
        self.assertEqual(f.md5, "abc123")
        self.assertEqual(f.update_ts, 1704067200.0)

    def test_compute_metadata(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sav") as tmp:
            tmp.write(b"test save data")
            tmp_path = tmp.name
        try:
            f = SyncFile(relative_path="test.sav", absolute_path=tmp_path)
            f.compute_metadata()

            # Verify MD5 is computed on gzip-compressed data
            compressed = gzip.compress(b"test save data", compresslevel=6, mtime=0)
            expected_md5 = hashlib.md5(compressed).hexdigest()
            self.assertEqual(f.md5, expected_md5)
            self.assertIsNotNone(f.update_time)
            self.assertIsNotNone(f.update_ts)
        finally:
            os.unlink(tmp_path)

    def test_compute_metadata_nonexistent_file(self):
        f = SyncFile(relative_path="missing.sav", absolute_path="/nonexistent/file")
        f.compute_metadata()
        self.assertIsNone(f.md5)
        self.assertIsNone(f.update_time)

    def test_repr(self):
        f = SyncFile(
            relative_path="test.sav",
            absolute_path="/tmp/test.sav",
            md5="abc123",
        )
        self.assertEqual(repr(f), "abc123 test.sav")


class TestSyncResult(unittest.TestCase):
    """Test the SyncResult dataclass."""

    def test_default_values(self):
        result = SyncResult()
        self.assertEqual(result.action, SyncAction.NONE)
        self.assertEqual(result.uploaded, [])
        self.assertEqual(result.downloaded, [])
        self.assertEqual(result.deleted_local, [])
        self.assertEqual(result.deleted_cloud, [])
        self.assertEqual(result.timestamp, 0.0)
        self.assertIsNone(result.error)


class TestGOGCloudStorageClient(unittest.TestCase):
    """Test the GOGCloudStorageClient class."""

    def setUp(self):
        self.client = GOGCloudStorageClient(
            user_id="12345",
            client_id="test_client_id",
            access_token="test_access_token",
        )

    def test_make_request_success(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"test": "data"}'
        mock_response.getheaders.return_value = [("Content-Type", "application/json")]

        with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response) as mock_urlopen:
            body, headers = self.client._make_request("GET", "/v1/test")

        self.assertEqual(body, b'{"test": "data"}')
        self.assertEqual(headers["Content-Type"], "application/json")
        mock_urlopen.assert_called_once()

    def test_make_request_404(self):
        import urllib.error

        error = urllib.error.HTTPError(url="http://test", code=404, msg="Not Found", hdrs={}, fp=None)

        with patch.object(_mod.urllib.request, "urlopen", side_effect=error):
            body, headers = self.client._make_request("GET", "/v1/missing")
        self.assertEqual(body, b"")
        self.assertEqual(headers, {})

    def test_make_request_http_error(self):
        import urllib.error

        error = urllib.error.HTTPError(url="http://test", code=500, msg="Server Error", hdrs={}, fp=None)

        with patch.object(_mod.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(HTTPError):
                self.client._make_request("GET", "/v1/test")

    def test_make_request_url_error(self):
        import urllib.error

        with patch.object(
            _mod.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with self.assertRaises(HTTPError):
                self.client._make_request("GET", "/v1/test")

    def test_list_files(self):
        cloud_data = [
            {
                "name": "saves/save1.sav",
                "hash": "abc123",
                "last_modified": "2024-01-15T10:30:00+00:00",
            },
            {
                "name": "saves/subdir/save2.sav",
                "hash": "def456",
                "last_modified": "2024-01-16T12:00:00+00:00",
            },
            {
                "name": "other/config.ini",
                "hash": "ghi789",
                "last_modified": "2024-01-14T08:00:00+00:00",
            },
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(cloud_data).encode()
        mock_response.getheaders.return_value = []

        with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
            files = self.client.list_files("saves")

        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].relative_path, "save1.sav")
        self.assertEqual(files[0].md5, "abc123")
        self.assertEqual(files[1].relative_path, "subdir/save2.sav")

    def test_list_files_empty(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.getheaders.return_value = []

        with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
            files = self.client.list_files("saves")
        self.assertEqual(files, [])

    def test_list_files_bad_json(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.getheaders.return_value = []

        with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
            files = self.client.list_files("saves")
        self.assertEqual(files, [])

    def test_upload_file(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.getheaders.return_value = []

        with tempfile.NamedTemporaryFile(delete=False, suffix=".sav") as tmp:
            tmp.write(b"save data content")
            tmp_path = tmp.name

        try:
            f = SyncFile(
                relative_path="game.sav",
                absolute_path=tmp_path,
                update_time="2024-01-15T10:00:00+00:00",
            )
            with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response) as mock_urlopen:
                result = self.client.upload_file(f, "saves")
            self.assertTrue(result)

            # Verify the PUT request was made
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            self.assertEqual(req.method, "PUT")
            self.assertIn("/saves/game.sav", req.full_url)
            self.assertEqual(req.get_header("Content-encoding"), "gzip")
        finally:
            os.unlink(tmp_path)

    def test_upload_nonexistent_file(self):
        f = SyncFile(
            relative_path="missing.sav",
            absolute_path="/nonexistent/missing.sav",
        )
        result = self.client.upload_file(f, "saves")
        self.assertFalse(result)

    def test_upload_file_http_error(self):
        import urllib.error

        with tempfile.NamedTemporaryFile(delete=False, suffix=".sav") as tmp:
            tmp.write(b"data")
            tmp_path = tmp.name

        try:
            f = SyncFile(
                relative_path="game.sav",
                absolute_path=tmp_path,
                update_time="2024-01-15T10:00:00+00:00",
            )
            with patch.object(
                _mod.urllib.request,
                "urlopen",
                side_effect=urllib.error.HTTPError(url="http://test", code=500, msg="Error", hdrs={}, fp=None),
            ):
                result = self.client.upload_file(f, "saves")
            self.assertFalse(result)
        finally:
            os.unlink(tmp_path)

    def test_download_file(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"save file content"
        mock_response.getheaders.return_value = [("X-Object-Meta-LocalLastModified", "2024-01-15T10:00:00+00:00")]

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = os.path.join(tmpdir, "saves", "game.sav")
            f = SyncFile(relative_path="game.sav", absolute_path=dest_path)

            with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
                result = self.client.download_file(f, "saves")
            self.assertTrue(result)
            self.assertTrue(os.path.exists(dest_path))
            with open(dest_path, "rb") as df:
                self.assertEqual(df.read(), b"save file content")

    def test_download_file_empty_response(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.getheaders.return_value = []

        f = SyncFile(relative_path="game.sav", absolute_path="/tmp/test.sav")
        with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
            result = self.client.download_file(f, "saves")
        self.assertFalse(result)

    def test_download_file_http_error(self):
        import urllib.error

        f = SyncFile(relative_path="game.sav", absolute_path="/tmp/test.sav")
        with patch.object(
            _mod.urllib.request,
            "urlopen",
            side_effect=urllib.error.HTTPError(url="http://test", code=403, msg="Forbidden", hdrs={}, fp=None),
        ):
            result = self.client.download_file(f, "saves")
        self.assertFalse(result)

    def test_download_file_invalid_timestamp(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"data"
        mock_response.getheaders.return_value = [("X-Object-Meta-LocalLastModified", "not a date")]

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = os.path.join(tmpdir, "game.sav")
            f = SyncFile(relative_path="game.sav", absolute_path=dest_path)

            with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
                result = self.client.download_file(f, "saves")
            self.assertTrue(result)

    def test_delete_file(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.getheaders.return_value = []

        f = SyncFile(relative_path="old.sav", absolute_path="/tmp/old.sav")
        with patch.object(_mod.urllib.request, "urlopen", return_value=mock_response):
            result = self.client.delete_file(f, "saves")
        self.assertTrue(result)

    def test_delete_file_error(self):
        import urllib.error

        f = SyncFile(relative_path="old.sav", absolute_path="/tmp/old.sav")
        with patch.object(
            _mod.urllib.request,
            "urlopen",
            side_effect=urllib.error.HTTPError(url="http://test", code=500, msg="Error", hdrs={}, fp=None),
        ):
            result = self.client.delete_file(f, "saves")
        self.assertFalse(result)


class TestSyncClassifier(unittest.TestCase):
    """Test the SyncClassifier class."""

    def test_classify_upload(self):
        """Files updated locally but not in cloud -> UPLOAD."""
        local = [
            SyncFile("a.sav", "/tmp/a.sav", md5="abc", update_ts=200.0),
        ]
        cloud = [
            SyncFile("a.sav", "", md5="old", update_ts=50.0),
        ]
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        action = classifier.get_action()
        self.assertEqual(action, SyncAction.UPLOAD)
        self.assertEqual(len(classifier.updated_local), 1)
        self.assertEqual(len(classifier.updated_cloud), 0)

    def test_classify_download(self):
        """Files updated in cloud but not locally -> DOWNLOAD."""
        local = [
            SyncFile("a.sav", "/tmp/a.sav", md5="abc", update_ts=50.0),
        ]
        cloud = [
            SyncFile("a.sav", "", md5="new", update_ts=200.0),
        ]
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        action = classifier.get_action()
        self.assertEqual(action, SyncAction.DOWNLOAD)
        self.assertEqual(len(classifier.updated_cloud), 1)
        self.assertEqual(len(classifier.updated_local), 0)

    def test_classify_conflict(self):
        """Files updated both locally and in cloud -> CONFLICT."""
        local = [
            SyncFile("a.sav", "/tmp/a.sav", md5="local", update_ts=200.0),
        ]
        cloud = [
            SyncFile("a.sav", "", md5="cloud", update_ts=200.0),
        ]
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        action = classifier.get_action()
        self.assertEqual(action, SyncAction.CONFLICT)

    def test_classify_none(self):
        """No files updated -> NONE."""
        local = [
            SyncFile("a.sav", "/tmp/a.sav", md5="same", update_ts=50.0),
        ]
        cloud = [
            SyncFile("a.sav", "", md5="same", update_ts=50.0),
        ]
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        action = classifier.get_action()
        self.assertEqual(action, SyncAction.NONE)

    def test_classify_new_local_file(self):
        """New local file not on cloud -> not_existing_remotely."""
        local = [
            SyncFile("new.sav", "/tmp/new.sav", md5="new", update_ts=200.0),
        ]
        cloud = []
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        self.assertEqual(len(classifier.not_existing_remotely), 1)

    def test_classify_new_cloud_file(self):
        """New cloud file not locally -> not_existing_locally."""
        local = []
        cloud = [
            SyncFile("new.sav", "", md5="new", update_ts=200.0),
        ]
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        self.assertEqual(len(classifier.not_existing_locally), 1)

    def test_classify_skips_empty_gzip_files(self):
        """Cloud files with empty gzip MD5 are skipped."""
        local = []
        cloud = [
            SyncFile("empty.sav", "", md5=EMPTY_GZIP_MD5, update_ts=200.0),
        ]
        classifier = SyncClassifier.classify(local, cloud, timestamp=100.0)
        self.assertEqual(len(classifier.not_existing_locally), 0)
        # Even if update_ts > timestamp, these should not appear as updated
        self.assertEqual(len(classifier.updated_cloud), 0)


class TestGetGameClientCredentials(unittest.TestCase):
    """Test the get_game_client_credentials function."""

    def test_success(self):
        builds_request = MagicMock()
        builds_request.json = {"items": [{"link": "https://cdn.gog.com/manifest.json"}]}

        manifest_data = {"clientId": "game_client_123", "clientSecret": "secret_abc"}
        manifest_request = MagicMock()
        manifest_request.content = json.dumps(manifest_data).encode()

        with patch.object(_mod, "Request", side_effect=[builds_request, manifest_request]):
            client_id, client_secret = get_game_client_credentials({"access_token": "token"}, "12345")
        self.assertEqual(client_id, "game_client_123")
        self.assertEqual(client_secret, "secret_abc")

    def test_zlib_compressed_manifest(self):
        builds_request = MagicMock()
        builds_request.json = {"items": [{"link": "https://cdn.gog.com/manifest.json"}]}

        manifest_data = {"clientId": "game_client_456", "clientSecret": ""}
        compressed_data = zlib.compress(json.dumps(manifest_data).encode())
        manifest_request = MagicMock()
        manifest_request.content = compressed_data

        with patch.object(_mod, "Request", side_effect=[builds_request, manifest_request]):
            client_id, client_secret = get_game_client_credentials({"access_token": "token"}, "67890")
        self.assertEqual(client_id, "game_client_456")
        self.assertEqual(client_secret, "")

    def test_no_builds(self):
        builds_request = MagicMock()
        builds_request.json = {"items": []}

        with patch.object(_mod, "Request", return_value=builds_request):
            with self.assertRaises(ValueError):
                get_game_client_credentials({"access_token": "token"}, "99999")

    def test_no_client_id_in_manifest(self):
        builds_request = MagicMock()
        builds_request.json = {"items": [{"link": "https://cdn.gog.com/manifest.json"}]}
        manifest_request = MagicMock()
        manifest_request.content = json.dumps({"version": "1.0"}).encode()

        with patch.object(_mod, "Request", side_effect=[builds_request, manifest_request]):
            with self.assertRaises(ValueError):
                get_game_client_credentials({"access_token": "token"}, "12345")

    def test_urls_fallback(self):
        """Test when 'link' is missing but 'urls' exists."""
        builds_request = MagicMock()
        builds_request.json = {"items": [{"urls": [{"url": "https://cdn.gog.com/manifest.json"}]}]}
        manifest_data = {"clientId": "from_urls", "clientSecret": "secret"}
        manifest_request = MagicMock()
        manifest_request.content = json.dumps(manifest_data).encode()

        with patch.object(_mod, "Request", side_effect=[builds_request, manifest_request]):
            client_id, _secret = get_game_client_credentials({"access_token": "token"}, "111")
        self.assertEqual(client_id, "from_urls")

    def test_no_manifest_url(self):
        """Test when neither 'link' nor 'urls' exist."""
        builds_request = MagicMock()
        builds_request.json = {"items": [{"id": "build_1"}]}

        with patch.object(_mod, "Request", return_value=builds_request):
            with self.assertRaises(ValueError):
                get_game_client_credentials({"access_token": "token"}, "333")


class TestGetGameScopedToken(unittest.TestCase):
    """Test the get_game_scoped_token function."""

    def test_success(self):
        mock_req = MagicMock()
        mock_req.json = {
            "access_token": "game_access_token",
            "refresh_token": "new_refresh",
            "user_id": "user_123",
            "expires_in": 3600,
        }

        with patch.object(_mod, "Request", return_value=mock_req):
            result = get_game_scoped_token("old_refresh", "client_id", "client_secret")
        self.assertEqual(result["access_token"], "game_access_token")
        self.assertEqual(result["user_id"], "user_123")


class TestGetCloudSaveLocations(unittest.TestCase):
    """Test the get_cloud_save_locations function."""

    def test_success(self):
        mock_req = MagicMock()
        mock_req.json = {
            "content": {
                "Windows": {
                    "cloudStorage": {
                        "enabled": True,
                        "locations": [
                            {
                                "name": "__default",
                                "location": (
                                    "<?APPLICATION_DATA_LOCAL?>/GOG.com/Galaxy/"
                                    "Applications/game123/Storage/Shared/Files"
                                ),
                            },
                            {
                                "name": "saves",
                                "location": "<?DOCUMENTS?>/My Games/TestGame/Saves",
                            },
                        ],
                    }
                }
            }
        }

        with patch.object(_mod, "Request", return_value=mock_req):
            locations = get_cloud_save_locations("token", "client123")
        self.assertEqual(len(locations), 2)
        self.assertEqual(locations[0].name, "__default")
        self.assertIn("<?APPLICATION_DATA_LOCAL?>", locations[0].location)
        self.assertEqual(locations[1].name, "saves")

    def test_cloud_storage_disabled(self):
        mock_req = MagicMock()
        mock_req.json = {
            "content": {
                "Windows": {
                    "cloudStorage": {
                        "enabled": False,
                        "locations": [],
                    }
                }
            }
        }

        with patch.object(_mod, "Request", return_value=mock_req):
            locations = get_cloud_save_locations("token", "client123")
        self.assertEqual(locations, [])

    def test_no_content(self):
        mock_req = MagicMock()
        mock_req.json = {}

        with patch.object(_mod, "Request", return_value=mock_req):
            locations = get_cloud_save_locations("token", "client123")
        self.assertEqual(locations, [])

    def test_http_error(self):
        with patch.object(_mod, "Request", side_effect=HTTPError("fail")):
            locations = get_cloud_save_locations("token", "client123")
        self.assertEqual(locations, [])


class TestResolveSavePath(unittest.TestCase):
    """Test the resolve_save_path function."""

    def test_native_linux_install_var(self):
        loc = CloudSaveLocation(name="saves", location="<?INSTALL?>/saves")
        result = resolve_save_path(loc, "/opt/games/mygame", is_native=True)
        self.assertEqual(result, "/opt/games/mygame/saves")

    def test_native_linux_documents_var(self):
        loc = CloudSaveLocation(name="saves", location="<?DOCUMENTS?>/My Games/Test")
        result = resolve_save_path(loc, "/opt/games/mygame", is_native=True)
        expected = os.path.normpath(str(Path.home() / "Documents" / "My Games" / "Test"))
        self.assertEqual(result, expected)

    def test_native_linux_appdata_local(self):
        loc = CloudSaveLocation(name="saves", location="<?APPLICATION_DATA_LOCAL?>/TestGame")
        result = resolve_save_path(loc, "/opt/games/mygame", is_native=True)
        expected = os.path.normpath(str(Path.home() / ".local" / "share" / "TestGame"))
        self.assertEqual(result, expected)

    def test_wine_userprofile_documents(self):
        loc = CloudSaveLocation(name="saves", location="<?DOCUMENTS?>/My Games/Test")
        result = resolve_save_path(
            loc,
            "/opt/games/mygame",
            is_native=False,
            wine_prefix="/home/user/.wine",
            wine_user="testuser",
        )
        expected = os.path.normpath("/home/user/.wine/drive_c/users/testuser/Documents/My Games/Test")
        self.assertEqual(result, expected)

    def test_wine_localappdata(self):
        loc = CloudSaveLocation(
            name="saves",
            location="<?APPLICATION_DATA_LOCAL?>/TestGame/Saves",
        )
        result = resolve_save_path(
            loc,
            "/opt/games/mygame",
            is_native=False,
            wine_prefix="/home/user/.wine",
            wine_user="testuser",
        )
        expected = os.path.normpath("/home/user/.wine/drive_c/users/testuser/AppData/Local/TestGame/Saves")
        self.assertEqual(result, expected)

    def test_wine_appdata_roaming(self):
        loc = CloudSaveLocation(
            name="saves",
            location="<?APPLICATION_DATA_ROAMING?>/TestGame",
        )
        result = resolve_save_path(
            loc,
            "/opt/games/mygame",
            is_native=False,
            wine_prefix="/home/user/.wine",
            wine_user="testuser",
        )
        expected = os.path.normpath("/home/user/.wine/drive_c/users/testuser/AppData/Roaming/TestGame")
        self.assertEqual(result, expected)

    def test_wine_no_prefix_returns_none(self):
        loc = CloudSaveLocation(name="saves", location="<?DOCUMENTS?>/Test")
        result = resolve_save_path(loc, "/opt/games/mygame", is_native=False)
        self.assertIsNone(result)

    def test_wine_default_user(self):
        loc = CloudSaveLocation(name="saves", location="<?INSTALL?>/saves")
        with patch.dict(os.environ, {"USER": "defaultwine"}):
            result = resolve_save_path(
                loc,
                "/opt/games/mygame",
                is_native=False,
                wine_prefix="/home/user/.wine",
            )
        self.assertIsNotNone(result)

    def test_unknown_variable_warns(self):
        loc = CloudSaveLocation(name="saves", location="<?UNKNOWN_VAR?>/saves")
        result = resolve_save_path(loc, "/opt/games/mygame", is_native=True)
        self.assertIsNotNone(result)
        # Should contain the variable name as-is (fallback)
        self.assertIn("UNKNOWN_VAR", result)


class TestCreateDirectoryMap(unittest.TestCase):
    """Test the create_directory_map function."""

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = create_directory_map(tmpdir)
            self.assertEqual(files, [])

    def test_nonexistent_directory(self):
        files = create_directory_map("/nonexistent/dir")
        self.assertEqual(files, [])

    def test_files_listed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.txt").touch()
            Path(tmpdir, "b.txt").touch()
            files = create_directory_map(tmpdir)
            self.assertEqual(len(files), 2)

    def test_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, "sub")
            subdir.mkdir()
            Path(tmpdir, "top.txt").touch()
            Path(subdir, "nested.txt").touch()
            files = create_directory_map(tmpdir)
            self.assertEqual(len(files), 2)
            self.assertTrue(any("nested.txt" in f for f in files))


class TestGetRelativePath(unittest.TestCase):
    """Test the get_relative_path function."""

    def test_basic(self):
        result = get_relative_path("/home/user/saves", "/home/user/saves/game.sav")
        self.assertEqual(result, "game.sav")

    def test_trailing_sep(self):
        result = get_relative_path("/home/user/saves/", "/home/user/saves/game.sav")
        self.assertEqual(result, "game.sav")

    def test_nested(self):
        result = get_relative_path("/saves", "/saves/sub/dir/file.sav")
        self.assertEqual(result, "sub/dir/file.sav")


class TestGOGCloudSync(unittest.TestCase):
    """Test the GOGCloudSync orchestrator class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ts_dir = tempfile.mkdtemp()  # Separate dir for timestamp files
        self.mock_service = MagicMock()
        self.mock_service.load_token.return_value = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
        }

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.ts_dir, ignore_errors=True)

    def test_load_save_timestamps(self):
        ts_path = os.path.join(self.tmpdir, "timestamps.json")
        ts_data = {"12345": {"saves": 1000.0}}
        with open(ts_path, "w") as f:
            json.dump(ts_data, f)

        with patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path):
            sync = GOGCloudSync(self.mock_service)
        self.assertEqual(sync.get_sync_timestamp("12345", "saves"), 1000.0)
        self.assertEqual(sync.get_sync_timestamp("12345", "other"), 0.0)
        self.assertEqual(sync.get_sync_timestamp("99999", "saves"), 0.0)

    def test_set_sync_timestamp(self):
        ts_path = os.path.join(self.tmpdir, "timestamps.json")

        with patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path):
            sync = GOGCloudSync(self.mock_service)
            sync.set_sync_timestamp("12345", "saves", 2000.0)

        # Load from disk
        with open(ts_path) as f:
            data = json.load(f)
        self.assertEqual(data["12345"]["saves"], 2000.0)

    def test_corrupt_timestamps_file(self):
        ts_path = os.path.join(self.tmpdir, "timestamps.json")
        with open(ts_path, "w") as f:
            f.write("not json")

        with patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path):
            sync = GOGCloudSync(self.mock_service)
        self.assertEqual(sync._sync_timestamps, {})

    def test_sync_token_load_failure(self):
        ts_path = os.path.join(self.tmpdir, "ts.json")
        self.mock_service.load_token.side_effect = Exception("no token")

        with patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path):
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves")
        self.assertIsNotNone(result.error)
        self.assertIn("credentials", result.error)

    def test_sync_client_credentials_failure(self):
        ts_path = os.path.join(self.tmpdir, "ts.json")

        with (
            patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path),
            patch.object(_mod, "get_game_client_credentials", side_effect=ValueError("no builds")),
        ):
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves")
        self.assertIsNotNone(result.error)
        self.assertIn("credentials", result.error)

    def test_sync_token_exchange_failure(self):
        ts_path = os.path.join(self.tmpdir, "ts.json")

        with (
            patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path),
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(_mod, "get_game_scoped_token", side_effect=HTTPError("auth fail")),
        ):
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves")
        self.assertIsNotNone(result.error)
        self.assertIn("token", result.error)

    def test_sync_invalid_token_response(self):
        ts_path = os.path.join(self.tmpdir, "ts.json")

        with (
            patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path),
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(_mod, "get_game_scoped_token", return_value={}),
        ):
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves")
        self.assertIsNotNone(result.error)
        self.assertIn("Invalid", result.error)

    def _create_sync_mocks(self, cloud_files=None, upload_ok=True, download_ok=True, delete_ok=True):
        """Helper to set up sync test mocks."""
        mock_client = MagicMock()
        mock_client.list_files.return_value = cloud_files or []
        mock_client.upload_file.return_value = upload_ok
        mock_client.download_file.return_value = download_ok
        mock_client.delete_file.return_value = delete_ok
        return mock_client

    def _sync_context(self, mock_client):
        """Helper returning tuple of context managers for sync tests."""
        ts_path = os.path.join(self.ts_dir, "ts.json")
        return (
            patch.object(GOGCloudSync, "_get_timestamp_path", return_value=ts_path),
            patch.object(_mod, "get_game_client_credentials", return_value=("cid", "csecret")),
            patch.object(
                _mod,
                "get_game_scoped_token",
                return_value={"access_token": "token", "user_id": "user1"},
            ),
            patch.object(_mod, "GOGCloudStorageClient", return_value=mock_client),
        )

    def test_sync_upload_when_no_cloud_files(self):
        """When cloud is empty and local has files, upload all."""
        mock_client = self._create_sync_mocks()

        save_file = os.path.join(self.tmpdir, "save.dat")
        with open(save_file, "w") as f:
            f.write("game data")

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves")

        self.assertEqual(result.action, SyncAction.UPLOAD)
        self.assertEqual(len(result.uploaded), 1)
        mock_client.upload_file.assert_called_once()

    def test_sync_download_when_no_local_files(self):
        """When local is empty and cloud has files, download all."""
        cloud_files = [
            SyncFile("save.dat", "", md5="abc123", update_ts=100.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        empty_dir = os.path.join(self.tmpdir, "empty")
        os.makedirs(empty_dir)

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", empty_dir, "saves")

        self.assertEqual(result.action, SyncAction.DOWNLOAD)
        self.assertEqual(len(result.downloaded), 1)

    def test_sync_creates_save_directory(self):
        """When save path doesn't exist, it gets created."""
        mock_client = self._create_sync_mocks()

        new_save_dir = os.path.join(self.tmpdir, "nonexistent", "saves")
        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            sync.sync_saves("12345", new_save_dir, "saves")

        self.assertTrue(os.path.exists(new_save_dir))

    def test_sync_force_upload(self):
        """Force upload should upload all local files."""
        cloud_files = [
            SyncFile("old.dat", "", md5="old", update_ts=5000.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        save_file = os.path.join(self.tmpdir, "save.dat")
        with open(save_file, "w") as f:
            f.write("new data")

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves", preferred_action="forceupload")
        self.assertEqual(result.action, SyncAction.UPLOAD)

    def test_sync_force_download(self):
        """Force download should download all cloud files."""
        cloud_files = [
            SyncFile("save.dat", "", md5="abc", update_ts=100.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        save_file = os.path.join(self.tmpdir, "local.dat")
        with open(save_file, "w") as f:
            f.write("local data")

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            result = sync.sync_saves("12345", self.tmpdir, "saves", preferred_action="forcedownload")
        self.assertEqual(result.action, SyncAction.DOWNLOAD)

    def test_sync_refused_upload_when_cloud_newer(self):
        """Upload refused when cloud has newer files."""
        cloud_files = [
            SyncFile("save.dat", "", md5="cloud", update_ts=5000.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        save_file = os.path.join(self.tmpdir, "save.dat")
        with open(save_file, "w") as f:
            f.write("old local data")
        os.utime(save_file, (50.0, 50.0))

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            sync.set_sync_timestamp("12345", "saves", 100.0)
            result = sync.sync_saves("12345", self.tmpdir, "saves", preferred_action="upload")
        self.assertEqual(result.action, SyncAction.NONE)

    def test_sync_conflict(self):
        """Both local and cloud updated -> CONFLICT."""
        cloud_files = [
            SyncFile("save.dat", "", md5="cloud_new", update_ts=5000.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        save_file = os.path.join(self.tmpdir, "save.dat")
        with open(save_file, "w") as f:
            f.write("local new data")

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            sync.set_sync_timestamp("12345", "saves", 100.0)
            result = sync.sync_saves("12345", self.tmpdir, "saves")
        self.assertEqual(result.action, SyncAction.CONFLICT)

    def test_sync_download_deletes_extra_local_files(self):
        """During download, extra local files not in cloud get deleted."""
        cloud_files = [
            SyncFile("cloud_only.dat", "", md5="cloud", update_ts=5000.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        extra_file = os.path.join(self.tmpdir, "extra_local.dat")
        with open(extra_file, "w") as f:
            f.write("extra")
        os.utime(extra_file, (50.0, 50.0))

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            sync.set_sync_timestamp("12345", "saves", 100.0)
            result = sync.sync_saves("12345", self.tmpdir, "saves")

        self.assertEqual(result.action, SyncAction.DOWNLOAD)
        self.assertIn("extra_local.dat", result.deleted_local)

    def test_sync_upload_deletes_cloud_files_missing_locally(self):
        """During upload, cloud files that are gone locally get deleted."""
        cloud_files = [
            SyncFile("cloud_only.dat", "", md5="old", update_ts=50.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        local_file = os.path.join(self.tmpdir, "new_local.dat")
        with open(local_file, "w") as f:
            f.write("new")

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            sync.set_sync_timestamp("12345", "saves", 100.0)
            result = sync.sync_saves("12345", self.tmpdir, "saves")

        self.assertEqual(result.action, SyncAction.UPLOAD)

    def test_sync_none_when_up_to_date(self):
        """When files haven't changed, action is NONE."""
        cloud_files = [
            SyncFile("save.dat", "", md5="same", update_ts=50.0),
        ]
        mock_client = self._create_sync_mocks(cloud_files=cloud_files)

        save_file = os.path.join(self.tmpdir, "save.dat")
        with open(save_file, "w") as f:
            f.write("same")
        os.utime(save_file, (50.0, 50.0))

        p1, p2, p3, p4 = self._sync_context(mock_client)
        with p1, p2, p3, p4:
            sync = GOGCloudSync(self.mock_service)
            sync.set_sync_timestamp("12345", "saves", 100.0)
            result = sync.sync_saves("12345", self.tmpdir, "saves")

        self.assertEqual(result.action, SyncAction.NONE)


if __name__ == "__main__":
    unittest.main()
