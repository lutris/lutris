"""GOG Cloud Save Synchronization

Implements the GOG Galaxy cloud storage protocol for save synchronization.
Allows uploading and downloading game saves to/from GOG's cloud storage.

Protocol reference: Based on GOG Galaxy Communication Service cloud storage API.

Endpoints:
    - Cloud Storage: https://cloudstorage.gog.com
    - Remote Config: https://remote-config.gog.com
    - Content System: https://content-system.gog.com
    - Auth: https://auth.gog.com
"""

import datetime
import gzip
import hashlib
import json
import os
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from enum import Enum
from gettext import gettext as _
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lutris.util.http import HTTPError, Request
from lutris.util.log import logger

# GOG Cloud Storage API endpoints
GOG_CLOUDSTORAGE_URL = "https://cloudstorage.gog.com"
GOG_CONTENT_SYSTEM_URL = "https://content-system.gog.com"
GOG_REMOTE_CONFIG_URL = "https://remote-config.gog.com"
GOG_AUTH_URL = "https://auth.gog.com"

# User-Agent mimicking GOG Galaxy client (required by cloud storage API)
GOG_CLOUD_USER_AGENT = (
    "GOGGalaxyCommunicationService/2.0.13.27 (Windows_32bit) dont_sync_marker/true installation_source/gog"
)

# MD5 hash of an empty gzip-compressed file — these are skipped during sync
EMPTY_GZIP_MD5 = "aadd86936a80ee8a369579c3926f1b3c"

# Default timeout for cloud storage API requests (seconds)
CLOUD_API_TIMEOUT = 30

LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo


class SyncAction(Enum):
    """Possible sync actions after comparing local and remote saves."""

    DOWNLOAD = 0
    UPLOAD = 1
    CONFLICT = 2
    NONE = 3


@dataclass
class CloudSaveLocation:
    """Represents a GOG cloud save location for a game.

    Attributes:
        name: The location identifier (e.g. '__default' or a specific name)
        location: The path template with GOG variables (e.g. '<?DOCUMENTS?>/My Games/...')
    """

    name: str
    location: str


@dataclass
class SyncFile:
    """Represents a file involved in cloud save synchronization.

    Attributes:
        relative_path: Path relative to the sync root (cloud file identifier).
            Uses forward slashes as separator.
        absolute_path: Full local filesystem path to the file.
        md5: MD5 hash of the gzip-compressed file content, or None if not yet computed.
        update_time: ISO 8601 timestamp of last modification, or None.
        update_ts: Unix timestamp of last modification, or None.
    """

    relative_path: str
    absolute_path: str
    md5: Optional[str] = None
    update_time: Optional[str] = None
    update_ts: Optional[float] = None

    def compute_metadata(self) -> None:
        """Compute md5 and update_time from the local file."""
        if not os.path.exists(self.absolute_path):
            return
        ts = os.stat(self.absolute_path).st_mtime
        date_time_obj = datetime.datetime.fromtimestamp(ts, tz=LOCAL_TIMEZONE).astimezone(datetime.timezone.utc)

        with open(self.absolute_path, "rb") as f:
            raw_data = f.read()
        compressed = gzip.compress(raw_data, compresslevel=6, mtime=0)
        self.md5 = hashlib.md5(compressed).hexdigest()
        self.update_time = date_time_obj.isoformat(timespec="seconds")
        self.update_ts = date_time_obj.timestamp()

    def __repr__(self) -> str:
        return f"{self.md5} {self.relative_path}"


@dataclass
class SyncResult:
    """Result of a cloud sync operation.

    Attributes:
        action: The sync action that was performed.
        uploaded: List of files that were uploaded.
        downloaded: List of files that were downloaded.
        deleted_local: List of local files that were deleted.
        deleted_cloud: List of cloud files that were deleted.
        timestamp: New sync timestamp after the operation.
        error: Error message if the sync failed, or None.
    """

    action: SyncAction = SyncAction.NONE
    uploaded: List[str] = field(default_factory=list)
    downloaded: List[str] = field(default_factory=list)
    deleted_local: List[str] = field(default_factory=list)
    deleted_cloud: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    error: Optional[str] = None


class GOGCloudStorageClient:
    """Client for GOG's cloud storage REST API.

    Handles file listing, upload, download, and deletion using
    the GOG Galaxy-compatible cloud storage protocol.
    """

    def __init__(self, user_id: str, client_id: str, access_token: str) -> None:
        self.user_id = user_id
        self.client_id = client_id
        self.access_token = access_token

    def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[bytes] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[bytes, Dict[str, str]]:
        """Make an authenticated request to the cloud storage API.

        Args:
            method: HTTP method (GET, PUT, DELETE).
            path: URL path after the base URL.
            data: Request body bytes for PUT requests.
            extra_headers: Additional headers to include.

        Returns:
            Tuple of (response_body_bytes, response_headers_dict).

        Raises:
            HTTPError: If the request fails.
        """
        url = f"{GOG_CLOUDSTORAGE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": GOG_CLOUD_USER_AGENT,
            "X-Object-Meta-User-Agent": GOG_CLOUD_USER_AGENT,
        }
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=CLOUD_API_TIMEOUT)
            response_body = response.read()
            response_headers = {k: v for k, v in response.getheaders()}
            response.close()
            return response_body, response_headers
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return b"", {}
            raise HTTPError(
                "Cloud storage API error: %s %s -> %s" % (method, url, error),
                code=error.code,
            ) from error
        except (urllib.error.URLError, OSError) as error:
            raise HTTPError("Cloud storage connection error: %s" % error) from error

    def list_files(self, dir_name: str) -> List[SyncFile]:
        """List all files in cloud storage under a given directory.

        Args:
            dir_name: The cloud save directory name (location name).

        Returns:
            List of SyncFile objects representing cloud files.
        """
        path = f"/v1/{self.user_id}/{self.client_id}"
        body, _ = self._make_request("GET", path, extra_headers={"Accept": "application/json"})

        if not body:
            return []

        try:
            json_data = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Failed to parse cloud file listing response")
            return []

        files = []
        for entry in json_data:
            name = entry.get("name", "")
            if not name.startswith(dir_name + "/"):
                continue
            relative_path = name.replace(f"{dir_name}/", "", 1)
            md5 = entry.get("hash")
            last_modified = entry.get("last_modified")
            logger.debug(
                "Cloud file found: %s (MD5: %s, modified: %s)",
                relative_path,
                md5,
                last_modified,
            )
            files.append(
                SyncFile(
                    relative_path=relative_path,
                    absolute_path="",  # Will be set later when resolving local path
                    md5=md5,
                    update_time=last_modified,
                    update_ts=(
                        datetime.datetime.fromisoformat(last_modified).astimezone().timestamp()
                        if last_modified
                        else None
                    ),
                )
            )
        logger.info("Found %d files in cloud for directory '%s'", len(files), dir_name)
        return files

    def upload_file(self, sync_file: SyncFile, dir_name: str) -> bool:
        """Upload a local file to cloud storage.

        The file is gzip-compressed and uploaded with metadata headers.

        Args:
            sync_file: The file to upload (must have absolute_path and metadata computed).
            dir_name: The cloud save directory name.

        Returns:
            True if upload succeeded, False otherwise.
        """
        if not os.path.exists(sync_file.absolute_path):
            logger.error("Cannot upload %s: file does not exist", sync_file.absolute_path)
            return False

        with open(sync_file.absolute_path, "rb") as f:
            raw_data = f.read()
        compressed_data = gzip.compress(raw_data, compresslevel=6, mtime=0)

        fpath = urllib.parse.quote(sync_file.relative_path)
        path = f"/v1/{self.user_id}/{self.client_id}/{dir_name}/{fpath}"

        headers = {
            "X-Object-Meta-LocalLastModified": sync_file.update_time or "",
            "Etag": hashlib.md5(compressed_data).hexdigest(),
            "Content-Encoding": "gzip",
        }

        try:
            response_body, response_headers = self._make_request(
                "PUT", path, data=compressed_data, extra_headers=headers
            )
            logger.info(
                "Upload SUCCESS: %s (size: %d bytes compressed, MD5: %s)",
                sync_file.relative_path,
                len(compressed_data),
                headers["Etag"],
            )
            return True
        except HTTPError as ex:
            logger.error("Upload FAILED: %s - %s", sync_file.relative_path, ex)
            return False

    def download_file(self, sync_file: SyncFile, dir_name: str) -> bool:
        """Download a file from cloud storage to local filesystem.

        Args:
            sync_file: The file to download (absolute_path must be set).
            dir_name: The cloud save directory name.

        Returns:
            True if download succeeded, False otherwise.
        """
        fpath = urllib.parse.quote(sync_file.relative_path)
        path = f"/v1/{self.user_id}/{self.client_id}/{dir_name}/{fpath}"

        logger.info("Downloading %s to %s", sync_file.relative_path, sync_file.absolute_path)

        try:
            body, headers = self._make_request("GET", path)
        except HTTPError as ex:
            logger.error("Failed to download %s: %s", sync_file.relative_path, ex)
            return False

        if not body:
            logger.error("Empty response when downloading %s", sync_file.relative_path)
            return False

        logger.info("Downloaded %d bytes (compressed) for %s", len(body), sync_file.relative_path)

        # Decompress the file - GOG stores saves as gzip-compressed
        try:
            decompressed_data = gzip.decompress(body)
            logger.info("Decompressed to %d bytes", len(decompressed_data))
        except Exception as ex:
            logger.error("Failed to decompress %s: %s", sync_file.relative_path, ex)
            return False

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(sync_file.absolute_path), exist_ok=True)

        try:
            with open(sync_file.absolute_path, "wb") as f:
                f.write(decompressed_data)
            logger.info("Successfully wrote %d bytes to %s", len(decompressed_data), sync_file.absolute_path)
        except Exception as ex:
            logger.error("Failed to write file %s: %s", sync_file.absolute_path, ex)
            return False

        # Restore file modification time from cloud metadata
        last_modified = headers.get("X-Object-Meta-LocalLastModified")
        if last_modified:
            try:
                f_timestamp = datetime.datetime.fromisoformat(last_modified).astimezone().timestamp()
                os.utime(sync_file.absolute_path, (f_timestamp, f_timestamp))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid LastModified header for %s: %s",
                    sync_file.relative_path,
                    last_modified,
                )

        logger.info("Download complete: %s", sync_file.relative_path)
        return True

    def delete_file(self, sync_file: SyncFile, dir_name: str) -> bool:
        """Delete a file from cloud storage.

        Args:
            sync_file: The file to delete.
            dir_name: The cloud save directory name.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        fpath = urllib.parse.quote(sync_file.relative_path)
        path = f"/v1/{self.user_id}/{self.client_id}/{dir_name}/{fpath}"

        try:
            self._make_request("DELETE", path)
            logger.debug("Deleted cloud file %s", sync_file.relative_path)
            return True
        except HTTPError as ex:
            logger.error("Failed to delete %s: %s", sync_file.relative_path, ex)
            return False


class SyncClassifier:
    """Classifies sync direction by comparing local and cloud files.

    Uses the last sync timestamp to determine which files have been
    updated since the last sync, and whether to upload, download,
    or flag a conflict.
    """

    def __init__(self) -> None:
        self.action: Optional[SyncAction] = None
        self.updated_local: List[SyncFile] = []
        self.updated_cloud: List[SyncFile] = []
        self.not_existing_locally: List[SyncFile] = []
        self.not_existing_remotely: List[SyncFile] = []

    def get_action(self) -> SyncAction:
        """Determine the sync action based on classified files."""
        if not self.updated_local and self.updated_cloud:
            self.action = SyncAction.DOWNLOAD
        elif self.updated_local and not self.updated_cloud:
            self.action = SyncAction.UPLOAD
        elif not self.updated_local and not self.updated_cloud:
            self.action = SyncAction.NONE
        else:
            self.action = SyncAction.CONFLICT
        return self.action

    @classmethod
    def classify(
        cls,
        local_files: List[SyncFile],
        cloud_files: List[SyncFile],
        timestamp: float,
    ) -> "SyncClassifier":
        """Classify files based on last sync timestamp.

        Args:
            local_files: List of local save files with metadata.
            cloud_files: List of cloud save files with metadata.
            timestamp: Unix timestamp of the last successful sync.

        Returns:
            A SyncClassifier with classified file lists.
        """
        classifier = cls()
        local_paths = {f.relative_path for f in local_files}
        cloud_paths = {f.relative_path for f in cloud_files}

        for f in local_files:
            if f.relative_path not in cloud_paths:
                classifier.not_existing_remotely.append(f)
            if f.update_ts is not None and f.update_ts > timestamp:
                classifier.updated_local.append(f)

        for f in cloud_files:
            if f.md5 == EMPTY_GZIP_MD5:
                continue
            if f.relative_path not in local_paths:
                classifier.not_existing_locally.append(f)
            if f.update_ts is not None and f.update_ts > timestamp:
                classifier.updated_cloud.append(f)

        return classifier


def get_game_client_credentials(gog_token: dict, game_id: str, platform: str = "windows") -> Tuple[str, str]:
    """Get the game-specific clientId and clientSecret from the build manifest.

    GOG cloud storage requires game-scoped credentials obtained from the
    game's build manifest on GOG's content system.

    Args:
        gog_token: The user's GOG token dict (must have 'access_token').
        game_id: The GOG game/product ID.
        platform: The game's platform ('windows', 'osx', 'linux').

    Returns:
        Tuple of (client_id, client_secret).

    Raises:
        HTTPError: If the build or manifest cannot be fetched.
        ValueError: If clientId/clientSecret not found in manifest.
    """
    # Step 1: Get builds list
    builds_url = f"{GOG_CONTENT_SYSTEM_URL}/products/{game_id}/os/{platform}/builds?generation=2"
    request = Request(builds_url)
    request.get()
    builds_data = request.json

    if not builds_data or not builds_data.get("items"):
        raise ValueError(f"No builds found for game {game_id} on {platform}")

    # Step 2: Get the build manifest
    meta_url = builds_data["items"][0].get("link")
    if not meta_url:
        # Try getting from URLs if link is not directly available
        urls = builds_data["items"][0].get("urls")
        if urls:
            meta_url = urls[0].get("url")

    if not meta_url:
        raise ValueError(f"No manifest URL found for game {game_id}")

    meta_request = Request(meta_url)
    meta_request.get()

    # Manifest may be zlib-compressed (generation 2)
    try:
        decompressed = zlib.decompress(meta_request.content)
        manifest = json.loads(decompressed)
    except zlib.error:
        manifest = json.loads(meta_request.content)

    client_id = manifest.get("clientId")
    client_secret = manifest.get("clientSecret")

    if not client_id:
        raise ValueError(f"No clientId found in manifest for game {game_id}")

    return client_id, client_secret or ""


def get_game_scoped_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    """Exchange a GOG refresh token for a game-scoped access token.

    The cloud storage API requires a token scoped to the game's clientId.

    Args:
        refresh_token: The user's GOG refresh token.
        client_id: The game's clientId from the build manifest.
        client_secret: The game's clientSecret from the build manifest.

    Returns:
        Dict with at minimum 'access_token', 'refresh_token', 'user_id'.

    Raises:
        HTTPError: If the token exchange fails.
    """
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "without_new_session": "1",
    }
    url = f"{GOG_AUTH_URL}/token?" + urllib.parse.urlencode(params)
    request = Request(url, redacted_query_parameters=("refresh_token",))
    request.get()
    return request.json


def get_cloud_save_locations(access_token: str, client_id: str, platform: str = "windows") -> List[CloudSaveLocation]:
    """Fetch cloud save locations from GOG's remote config API.

    Args:
        access_token: A valid GOG access token.
        client_id: The game's clientId.
        platform: The platform to query ('windows', 'osx', or 'linux' - lowercase).

    Returns:
        List of CloudSaveLocation objects, or empty list if cloud saves
        are not enabled for this game.
    """
    url = f"{GOG_REMOTE_CONFIG_URL}/components/galaxy_client/clients/{client_id}?component_version=2.0.45"
    try:
        request = Request(url)
        request.get()
        data = request.json
    except HTTPError as ex:
        logger.error("Failed to get remote config for client %s: %s", client_id, ex)
        return []

    logger.debug("Remote config API response: %s", json.dumps(data, indent=2)[:500])

    if not data or "content" not in data:
        logger.warning("No 'content' field in remote config response")
        return []

    # Log ALL available platform keys to debug platform mismatch
    available_platforms = list(data["content"].keys()) if "content" in data else []
    logger.info("Available platforms in API response: %s", available_platforms)
    logger.info("Requested platform: %s", platform)

    # Remote-config API uses capitalized platform names (Windows, Linux, MacOS)
    # Map lowercase input to capitalized API names
    platform_map = {
        "windows": "Windows",
        "linux": "Linux",
        "osx": "MacOS",
    }
    api_platform = platform_map.get(platform.lower(), platform)

    platform_data = data["content"].get(api_platform, {})
    logger.debug("Platform '%s' data keys: %s", api_platform, list(platform_data.keys()) if platform_data else "empty")

    # Fallback: try case-insensitive match if exact match fails
    if not platform_data:
        for p in available_platforms:
            if p.lower() == platform.lower():
                logger.info("Found case-insensitive platform match: %s -> %s", platform, p)
                platform_data = data["content"][p]
                api_platform = p
                break

    cloud_storage = platform_data.get("cloudStorage", {})
    logger.debug("cloudStorage config: %s", cloud_storage)

    if not cloud_storage.get("enabled"):
        logger.info("Cloud storage not enabled for client %s platform %s", client_id, api_platform)
        return []

    locations = []
    for loc in cloud_storage.get("locations", []):
        locations.append(
            CloudSaveLocation(
                name=loc.get("name", "__default"),
                location=loc.get("location", ""),
            )
        )
    return locations


# GOG save path variable mapping
GOG_VARIABLE_MAP_LINUX_NATIVE = {
    "INSTALL": "",  # Will be set per-game
    "DOCUMENTS": str(Path.home() / "Documents"),
    "APPLICATION_DATA_LOCAL": str(Path.home() / ".local" / "share"),
    "APPLICATION_DATA_LOCAL_LOW": str(Path.home() / ".local" / "share"),
    "APPLICATION_DATA_ROAMING": str(Path.home() / ".config"),
    "SAVED_GAMES": str(Path.home() / ".local" / "share"),
    "APPLICATION_SUPPORT": "",  # Not applicable on Linux
}

# For Windows games under Wine, these map to Windows env vars
# that get resolved within the Wine prefix
GOG_VARIABLE_MAP_WINE = {
    "INSTALL": "",  # Will be set per-game
    "DOCUMENTS": "%USERPROFILE%\\Documents",
    "SAVED_GAMES": "%USERPROFILE%\\Saved Games",
    "APPLICATION_DATA_LOCAL": "%LOCALAPPDATA%",
    "APPLICATION_DATA_LOCAL_LOW": "%APPDATA%\\..\\LocalLow",
    "APPLICATION_DATA_ROAMING": "%APPDATA%",
    "APPLICATION_SUPPORT": "",  # Not applicable
}


def resolve_save_path(
    location: CloudSaveLocation,
    install_path: str,
    is_native: bool = False,
    wine_prefix: Optional[str] = None,
    wine_user: Optional[str] = None,
) -> Optional[str]:
    """Resolve a GOG cloud save location to an absolute filesystem path.

    Replaces GOG variables (<?INSTALL?>, <?DOCUMENTS?>, etc.) with
    actual filesystem paths.

    Args:
        location: The cloud save location with variable placeholders.
        install_path: The game's installation directory.
        is_native: True if the game is a native Linux game.
        wine_prefix: Path to the Wine prefix (for Windows games).
        wine_user: The Wine user name (defaults to current user).

    Returns:
        Resolved absolute path, or None if resolution fails.
    """
    path_template = location.location

    if is_native:
        var_map = GOG_VARIABLE_MAP_LINUX_NATIVE.copy()
    else:
        var_map = GOG_VARIABLE_MAP_WINE.copy()
    var_map["INSTALL"] = install_path

    # Replace GOG variables <?NAME?> with resolved values
    import re

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)
        resolved = var_map.get(var_name)
        if resolved is None:
            logger.warning("Unknown GOG save path variable: %s", var_name)
            return var_name
        return resolved

    resolved = re.sub(r"<\?(\w+)\?>", replace_var, path_template)

    if is_native:
        # For native Linux games, expand shell variables and normalize
        resolved = os.path.expandvars(os.path.expanduser(resolved))
        return os.path.normpath(resolved)

    # For Wine games, resolve Windows paths within the Wine prefix
    if not wine_prefix:
        logger.error("Wine prefix required for resolving Windows save paths")
        return None

    if not wine_user:
        wine_user = os.environ.get("USER", "steamuser")

    # Resolve Windows environment variables to Wine prefix paths
    wine_drive_c = os.path.join(wine_prefix, "drive_c")
    wine_users = os.path.join(wine_drive_c, "users", wine_user)

    resolved = resolved.replace("\\", "/")
    resolved = resolved.replace("%USERPROFILE%", wine_users)
    resolved = resolved.replace("%LOCALAPPDATA%", os.path.join(wine_users, "AppData", "Local"))
    resolved = resolved.replace("%APPDATA%", os.path.join(wine_users, "AppData", "Roaming"))

    return os.path.normpath(resolved)


def create_directory_map(path: str) -> List[str]:
    """Recursively list all files in a directory.

    Args:
        path: Root directory to scan.

    Returns:
        List of absolute file paths.
    """
    files = []
    if not os.path.exists(path):
        return files
    for entry in os.listdir(path):
        abs_path = os.path.join(path, entry)
        if os.path.isdir(abs_path):
            files.extend(create_directory_map(abs_path))
        else:
            files.append(abs_path)
    return files


def get_relative_path(root: str, path: str) -> str:
    """Get the relative path from a root directory, using forward slashes.

    Args:
        root: The root directory path.
        path: The full path to make relative.

    Returns:
        Relative path using forward slashes.
    """
    if not root.endswith(os.sep) and not root.endswith("/"):
        root = root + os.sep
    return path.replace(root, "").replace("\\", "/")


class GOGCloudSync:
    """Orchestrates cloud save synchronization for GOG games.

    Coordinates between the local filesystem and GOG's cloud storage
    to keep game saves in sync.
    """

    def __init__(self, gog_service: Any) -> None:
        """Initialize the cloud sync orchestrator.

        Args:
            gog_service: An instance of GOGService with active authentication.
        """
        self.gog_service = gog_service
        self._sync_timestamps: Dict[str, Dict[str, float]] = {}
        self._load_sync_timestamps()

    def _get_timestamp_path(self) -> str:
        """Return the path to the sync timestamps file."""
        from lutris import settings

        return os.path.join(settings.CACHE_DIR, "gog_cloud_sync_timestamps.json")

    def _load_sync_timestamps(self) -> None:
        """Load sync timestamps from disk."""
        ts_path = self._get_timestamp_path()
        if os.path.exists(ts_path):
            try:
                with open(ts_path, encoding="utf-8") as f:
                    self._sync_timestamps = json.load(f)
            except (json.JSONDecodeError, OSError) as ex:
                logger.warning("Failed to load sync timestamps: %s", ex)
                self._sync_timestamps = {}

    def _save_sync_timestamps(self) -> None:
        """Save sync timestamps to disk."""
        ts_path = self._get_timestamp_path()
        try:
            os.makedirs(os.path.dirname(ts_path), exist_ok=True)
            with open(ts_path, "w", encoding="utf-8") as f:
                json.dump(self._sync_timestamps, f)
        except OSError as ex:
            logger.error("Failed to save sync timestamps: %s", ex)

    def get_sync_timestamp(self, game_id: str, location_name: str) -> float:
        """Get the last sync timestamp for a game's save location.

        Args:
            game_id: The GOG game ID.
            location_name: The save location name.

        Returns:
            Unix timestamp of last sync, or 0.0 if never synced.
        """
        return self._sync_timestamps.get(game_id, {}).get(location_name, 0.0)

    def set_sync_timestamp(self, game_id: str, location_name: str, timestamp: float) -> None:
        """Set the sync timestamp for a game's save location.

        Args:
            game_id: The GOG game ID.
            location_name: The save location name.
            timestamp: Unix timestamp to set.
        """
        if game_id not in self._sync_timestamps:
            self._sync_timestamps[game_id] = {}
        self._sync_timestamps[game_id][location_name] = timestamp
        self._save_sync_timestamps()

    def sync_saves(
        self,
        game_id: str,
        save_path: str,
        location_name: str,
        platform: str = "windows",
        preferred_action: Optional[str] = None,
    ) -> SyncResult:
        """Synchronize saves for a specific game and save location.

        Args:
            game_id: The GOG game/product ID.
            save_path: The resolved local save directory path.
            location_name: The cloud save directory name.
            platform: The game platform ('windows', 'osx', 'linux').
            preferred_action: Force a specific action ('upload', 'download',
                'forceupload', 'forcedownload'), or None for automatic.

        Returns:
            SyncResult with details of what was done.
        """
        result = SyncResult()

        # Ensure save directory exists
        if not os.path.exists(save_path):
            logger.info("Save path does not exist, creating: %s", save_path)
            os.makedirs(save_path, exist_ok=True)

        # Step 1: Get GOG token
        try:
            token = self.gog_service.load_token()
        except Exception as ex:
            result.error = _("Failed to load GOG credentials: %s") % str(ex)
            logger.error(result.error)
            return result

        # Step 2: Get game-scoped credentials
        try:
            client_id, client_secret = get_game_client_credentials(token, game_id, platform)
        except (HTTPError, ValueError) as ex:
            result.error = _("Failed to get game credentials: %s") % str(ex)
            logger.error(result.error)
            return result

        # Step 3: Get game-scoped access token
        try:
            game_token = get_game_scoped_token(token["refresh_token"], client_id, client_secret)
        except HTTPError as ex:
            result.error = _("Failed to get game-scoped token: %s") % str(ex)
            logger.error(result.error)
            return result

        user_id = game_token.get("user_id", "")
        access_token = game_token.get("access_token", "")

        if not user_id or not access_token:
            result.error = _("Invalid game token response: missing user_id or access_token")
            logger.error(result.error)
            return result

        # Step 4: Create cloud storage client
        client = GOGCloudStorageClient(user_id, client_id, access_token)

        # Step 5: Scan local files
        dir_list = create_directory_map(save_path)
        local_files = [
            SyncFile(
                relative_path=get_relative_path(save_path, f),
                absolute_path=f,
            )
            for f in dir_list
        ]
        for f in local_files:
            f.compute_metadata()

        logger.info("Local files: %d", len(local_files))

        # Step 6: Get cloud files
        cloud_files = client.list_files(location_name)
        # Set absolute paths for cloud files
        for cf in cloud_files:
            cf.absolute_path = os.path.join(save_path, cf.relative_path.replace("/", os.sep))

        downloadable_cloud = [f for f in cloud_files if f.md5 != EMPTY_GZIP_MD5]
        logger.info("Cloud files: %d", len(cloud_files))

        # Step 7: Handle trivial cases
        if local_files and not cloud_files:
            logger.info("No files in cloud, uploading all local files")
            action = SyncAction.UPLOAD
            for f in local_files:
                if client.upload_file(f, location_name):
                    result.uploaded.append(f.relative_path)
            result.action = action
            result.timestamp = datetime.datetime.now().timestamp()
            self.set_sync_timestamp(game_id, location_name, result.timestamp)
            return result

        if not local_files and cloud_files:
            logger.info("No local files, downloading all cloud files")
            action = SyncAction.DOWNLOAD
            for f in downloadable_cloud:
                if client.download_file(f, location_name):
                    result.downloaded.append(f.relative_path)
            result.action = action
            result.timestamp = datetime.datetime.now().timestamp()
            self.set_sync_timestamp(game_id, location_name, result.timestamp)
            return result

        # Step 8: Classify sync direction
        timestamp = self.get_sync_timestamp(game_id, location_name)
        classifier = SyncClassifier.classify(local_files, cloud_files, timestamp)
        action = classifier.get_action()

        # Step 9: Handle preferred action overrides
        if preferred_action:
            if preferred_action == "forceupload":
                logger.warning("Forcing upload")
                classifier.updated_local = local_files
                action = SyncAction.UPLOAD
            elif preferred_action == "forcedownload":
                logger.warning("Forcing download")
                classifier.updated_cloud = downloadable_cloud
                action = SyncAction.DOWNLOAD
            elif preferred_action == "upload" and action == SyncAction.DOWNLOAD:
                logger.warning("Refused to upload: newer files in cloud")
                result.action = SyncAction.NONE
                return result
            elif preferred_action == "download" and action == SyncAction.UPLOAD:
                logger.warning("Refused to download: newer files locally")
                result.action = SyncAction.NONE
                return result

        # Step 10: Execute sync
        if action == SyncAction.UPLOAD:
            logger.info("Uploading %d files", len(classifier.updated_local))
            for f in classifier.updated_local:
                if client.upload_file(f, location_name):
                    result.uploaded.append(f.relative_path)
            for f in classifier.not_existing_locally:
                if client.delete_file(f, location_name):
                    result.deleted_cloud.append(f.relative_path)

        elif action == SyncAction.DOWNLOAD:
            logger.info("Downloading %d files", len(classifier.updated_cloud))
            for f in classifier.updated_cloud:
                if client.download_file(f, location_name):
                    result.downloaded.append(f.relative_path)
            for f in classifier.not_existing_remotely:
                logger.info("Deleting local file: %s", f.absolute_path)
                try:
                    os.remove(f.absolute_path)
                    result.deleted_local.append(f.relative_path)
                except OSError as ex:
                    logger.error("Failed to delete %s: %s", f.absolute_path, ex)

        elif action == SyncAction.CONFLICT:
            logger.warning("Save files are in conflict — user action required")

        elif action == SyncAction.NONE:
            logger.info("Saves are up to date, nothing to do")

        result.action = action
        if action != SyncAction.CONFLICT:
            result.timestamp = datetime.datetime.now().timestamp()
            self.set_sync_timestamp(game_id, location_name, result.timestamp)

        return result
