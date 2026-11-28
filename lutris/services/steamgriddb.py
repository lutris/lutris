"""Resolve original Steam artwork through exact SteamGridDB title matches."""

import hashlib
import io
import json
import os
import re
import tempfile
import time
import urllib.request
import warnings
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from PIL import Image, UnidentifiedImageError

from lutris import settings
from lutris.util import http
from lutris.util.log import logger

API_URL = "https://www.steamgriddb.com/api/v2"
CACHE_TTL = 7 * 24 * 3600
REQUEST_INTERVAL = 1.0
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000


@dataclass
class ArtworkLookup:
    """Lookup outcome and original artwork URLs keyed by banner/cover/icon."""

    status: str
    urls: dict[str, str]


class _StopBatch(Exception):
    """Authentication or rate limit failure, do not send further requests."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not leak authorization or follow an asset redirect off the trusted host.
        raise http.HTTPError("SteamGridDB redirect refused", code=code)


class _Request(http.Request):
    """Bound buffering locally, without changing the shared HTTP client."""

    def __init__(self, url, **kwargs):
        super().__init__(url, **kwargs)
        self.opener = http.get_opener(url, _NoRedirect())
        self.buffer_size = 64 * 1024

    def _iter_chunks(self, request):
        try:
            if self.total_size and self.total_size > MAX_BYTES:
                raise ValueError("Artwork response too large")
            for chunk in super()._iter_chunks(request):
                if self.downloaded_size > MAX_BYTES:
                    raise ValueError("Artwork response too large")
                yield chunk
        finally:
            request.close()


def _valid_id(value):
    return type(value) is int and value > 0


def _asset_url(value):
    if not isinstance(value, str):
        return False
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        return (
            parts.scheme == "https"
            and host in ("shared.steamstatic.com", "cdn.cloudflare.steamstatic.com")
            and not parts.username
            and not parts.password
            and parts.port in (None, 443)
            and not parts.query
            and not parts.fragment
            and "\\" not in value
            and all(ord(char) > 32 for char in value)
        )
    except ValueError:
        return False


def _normalize(name):
    return name.strip().casefold() if isinstance(name, str) else ""


class _API:
    def __init__(self, key):
        self.key = key
        self.last_request = None
        self.results = {}
        self.cache_dir = Path(settings.CACHE_DIR) / "steamgriddb"

    def get(self, endpoint):
        if not isinstance(endpoint, str) or not endpoint.startswith("/") or endpoint.startswith("//"):
            return None
        if endpoint in self.results:
            return self.results[endpoint]
        path = self.cache_dir / (hashlib.sha256(endpoint.encode()).hexdigest() + ".json")
        try:
            info = path.stat()
            if 0 <= time.time() - info.st_mtime < CACHE_TTL and info.st_size <= 64 * 1024:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, (list, dict)):
                    self.results[endpoint] = data
                    return data
        except (OSError, ValueError):
            pass
        self.results[endpoint] = None
        if self.last_request is not None:
            time.sleep(max(0, REQUEST_INTERVAL - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            response = _Request(API_URL + endpoint, headers={"Authorization": "Bearer " + self.key}).get()
            if response.status_code in (401, 429):
                raise _StopBatch("authentication rejected" if response.status_code == 401 else "rate limited")
            if response.status_code == 404:
                raise http.HTTPError("No match", code=404)
            envelope = response.json
            if (
                response.status_code != 200
                or not isinstance(envelope, dict)
                or envelope.get("success") is not True
                or not isinstance(envelope.get("data"), (list, dict))
            ):
                logger.debug("SteamGridDB API returned an invalid envelope or status")
                return None
            data = envelope["data"]
        except http.UnauthorizedAccessError:
            raise _StopBatch("authentication rejected") from None
        except http.HTTPError as error:
            if error.code in (401, 429):
                raise _StopBatch("authentication rejected" if error.code == 401 else "rate limited") from None
            if error.code != 404:
                logger.debug("SteamGridDB API request failed (HTTP %s)", error.code)
                return None
            data = []
        except (OSError, ValueError) as error:
            logger.debug("SteamGridDB API request failed (%s)", type(error).__name__)
            return None
        self.results[endpoint] = data
        try:
            encoded = json.dumps(data).encode()
            if len(encoded) > 64 * 1024:
                return data
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Bound cache size, including old entries left by library removals.
            entries = sorted(self.cache_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)
            for old in entries[: max(0, len(entries) - 2047)]:
                old.unlink()
            with tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False) as temporary:
                temp_path = temporary.name
                temporary.write(encoded)
            try:
                os.replace(temp_path, path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except OSError:
            logger.debug("SteamGridDB API cache could not be written")
        return data


def _asset_path(value):
    """Accept relative metadata filenames, never URLs or traversal."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        return None
    segments = value.split("/")
    if any(segment in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_. -]+", segment) for segment in segments):
        return None
    return "/".join(quote(segment, safe="") for segment in segments)


def _language_path(values):
    if not isinstance(values, dict):
        return None
    english = _asset_path(values.get("english"))
    if english:
        return english
    return next((path for value in values.values() if (path := _asset_path(value))), None)


def _original_urls(entry):
    if not isinstance(entry, dict):
        return None
    app_id = entry.get("id")
    if not isinstance(app_id, str) or not re.fullmatch(r"[1-9][0-9]*", app_id):
        return None
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        return None
    base = f"https://shared.steamstatic.com/store_item_assets/steam/apps/{app_id}/"
    urls = {}
    header = _language_path(metadata.get("header_image_full"))
    if header:
        urls["banner"] = base + header
    capsule = metadata.get("library_capsule_full")
    if isinstance(capsule, dict):
        cover = _language_path(capsule.get("image2x")) or _language_path(capsule.get("image"))
        if cover:
            urls["cover"] = base + cover
    icon = metadata.get("icon")
    if isinstance(icon, str) and re.fullmatch(r"[A-Fa-f0-9]{40}", icon):
        urls["icon"] = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{icon}.jpg"
    return (app_id, urls) if urls else None


def lookup_artwork(title: str, api: _API | None = None) -> ArtworkLookup:
    """Resolve an exact title, propagating _StopBatch on authentication/rate limits."""
    if api is None:
        key = settings.read_setting("steamgriddb_api_key")
        if not isinstance(key, str) or not key.strip():
            return ArtworkLookup("missing_key", {})
        api = _API(key.strip())
    if not _normalize(title):
        return ArtworkLookup("no_match", {})
    data = api.get("/search/autocomplete/" + quote(title.strip(), safe=""))
    if not isinstance(data, list):
        return ArtworkLookup("error", {})
    if any(
        not isinstance(item, dict) or not _valid_id(item.get("id")) or not isinstance(item.get("name"), str)
        for item in data
    ):
        return ArtworkLookup("error", {})
    matches = [item for item in data if _normalize(item["name"]) == _normalize(title)]
    if not matches:
        return ArtworkLookup("no_match", {})
    if len(matches) != 1:
        return ArtworkLookup("ambiguous", {})
    game_id = matches[0]["id"]
    details = api.get(f"/games/id/{game_id}?platformdata=steam")
    if details == []:
        return ArtworkLookup("no_assets", {})
    if not isinstance(details, dict) or not _valid_id(details.get("id")) or details["id"] != game_id:
        return ArtworkLookup("error", {})
    platforms = details.get("external_platform_data")
    if platforms is None:
        return ArtworkLookup("no_assets", {})
    if not isinstance(platforms, dict):
        return ArtworkLookup("error", {})
    steam = platforms.get("steam")
    if steam is None:
        return ArtworkLookup("no_assets", {})
    if not isinstance(steam, list):
        return ArtworkLookup("error", {})
    originals = [original for entry in steam if (original := _original_urls(entry))]
    if not originals:
        return ArtworkLookup("no_assets", {})
    # Multiple editions with originals cannot be distinguished by title alone.
    if len({app_id for app_id, urls in originals}) != 1:
        return ArtworkLookup("ambiguous", {})
    originals.sort(key=lambda item: (-len(item[1]), sorted(item[1].items())))
    return ArtworkLookup("success", originals[0][1])


def encode_artwork(content: bytes, kind: str) -> bytes | None:
    """Validate static PNG/JPEG/WebP bytes and transcode without resizing or filesystem writes."""
    if kind not in ("banner", "cover", "icon") or not isinstance(content, bytes) or not content:
        return None
    if len(content) > MAX_BYTES:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in ("PNG", "JPEG", "WEBP")
                    or image.width * image.height > MAX_PIXELS
                    or getattr(image, "is_animated", False)
                ):
                    logger.debug("Artwork format, dimensions or animation rejected")
                    return None
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                image = image.convert("RGBA" if kind == "icon" else "RGB")
                output = io.BytesIO()
                image.save(output, format="PNG" if kind == "icon" else "JPEG")
                return output.getvalue() if output.tell() <= MAX_BYTES else None
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        logger.debug("Artwork could not be decoded (%s)", type(error).__name__)
    return None


def download_artwork(url: str, kind: str) -> bytes | None:
    """Fetch Valve-hosted originals, validating with the shared pure encoder."""
    if kind not in ("banner", "cover", "icon") or not _asset_url(url):
        return None
    # Also reject encoded traversal supplied directly to this public boundary.
    if _asset_path(unquote(urlsplit(url).path).lstrip("/")) is None:
        return None
    try:
        response = _Request(url).get()  # Never attach API credentials to Steam CDN requests.
        if response.status_code in (401, 429):
            raise _StopBatch("authentication rejected" if response.status_code == 401 else "rate limited")
        if response.status_code != 200:
            logger.debug("Steam artwork response was unsuccessful")
            return None
        return encode_artwork(response.content, kind)
    except http.UnauthorizedAccessError:
        raise _StopBatch("authentication rejected") from None
    except http.HTTPError as error:
        if error.code in (401, 429):
            raise _StopBatch("authentication rejected" if error.code == 401 else "rate limited") from None
        logger.debug("Steam artwork request failed (HTTP %s)", error.code)
    except (OSError, ValueError) as error:
        logger.debug("Steam artwork request failed (%s)", type(error).__name__)
    return None
