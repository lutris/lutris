"""Per-game artwork ownership, provider selection and atomic publication."""

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lutris import settings
from lutris.database import games
from lutris.gui.widgets.utils import MEDIA_CACHE_INVALIDATED
from lutris.services import steamgriddb
from lutris.services.service_media import MediaPath
from lutris.util import http

ARTWORK_LOCK = threading.RLock()
_BATCH_LOCK = threading.Lock()
_FILES = {"banner": "banner.jpg", "cover": "cover.jpg", "icon": "icon.png"}
_FLAGS = {"banner": "has_custom_banner", "cover": "has_custom_coverart_big", "icon": "has_custom_icon"}
_ERRORS = (OSError, ValueError, http.HTTPError, http.UnauthorizedAccessError)
_MAX_BYTES = 10 * 1024 * 1024


@dataclass
class RefreshResult:
    status: str
    updated_kinds: tuple[str, ...]
    game_id: str
    title: str
    source: str


def get_effective_source(game_data) -> str:
    override = game_data.get("artwork_source")
    source = override if override is not None else settings.read_setting("artwork_source")
    return source if source in ("lutris", "steamgriddb") else "lutris"


def _directory(game_id):
    game_id = str(game_id)
    if not game_id.isascii() or not game_id.isdecimal() or int(game_id) <= 0:
        raise ValueError("Artwork requires a library game ID")
    return Path(settings.DATA_DIR) / "artwork" / str(int(game_id))


def _path(game_id, kind, custom=False):
    return _directory(game_id) / ("custom" if custom else "auto") / _FILES[kind]


def get_game_media_paths(game_data, service_media, *, kind=None) -> list[MediaPath]:
    """Prefer the selected private slot, retaining legacy compatibility reads."""
    if kind is None:
        kind = {"coverart": "cover"}.get(service_media.api_field, service_media.api_field)
    legacy = service_media.get_possible_media_paths(game_data["slug"])
    if kind not in _FILES:
        return legacy
    if not game_data.get("id"):
        return legacy
    custom = bool(game_data.get(_FLAGS[kind]))
    return [
        MediaPath(str(_path(game_data["id"], kind, custom)), service_media),
        *legacy,
    ]


def _read_provenance(game_id):
    try:
        value = json.loads((_directory(game_id) / "provenance.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name, delete=False) as output:
            temporary = output.name
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _decode(data, kind):
    encoded = steamgriddb.encode_artwork(data, kind)
    if encoded is None:
        raise ValueError("Invalid artwork")
    return encoded


def _current(game):
    current = games.get_game_by_field(game["id"], "id")
    if (
        current
        and current.get("name") == game.get("name")
        and current.get("artwork_source") == game.get("artwork_source")
        and get_effective_source(current) == game["_source"]
    ):
        return current
    return None


def _fresh(game, kind):
    try:
        entry = _read_provenance(game["id"]).get(kind, {})
        return (
            isinstance(entry, dict)
            and entry.get("source") == game["_source"]
            and entry.get("title") == game.get("name")
            and entry.get("sha256") == hashlib.sha256(_path(game["id"], kind).read_bytes()).hexdigest()
        )
    except OSError:
        return False


def _publish(game, kind, data, *, reset=False):
    data = _decode(data, kind)
    with ARTWORK_LOCK:
        current = _current(game)
        if not current or (bool(current.get(_FLAGS[kind])) != bool(game.get(_FLAGS[kind]))):
            return False
        if current.get(_FLAGS[kind]) and not reset:
            return False
        metadata = _read_provenance(game["id"])
        # Invalidate provenance first: interrupted publication must be retried.
        metadata.pop(kind, None)
        provenance = _directory(game["id"]) / "provenance.json"
        _atomic_write(provenance, json.dumps(metadata).encode())
        _atomic_write(_path(game["id"], kind), data)
        metadata[kind] = {
            "source": game["_source"],
            "title": game.get("name"),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        _atomic_write(provenance, json.dumps(metadata).encode())
        if reset:
            games.update_existing(id=game["id"], **{_FLAGS[kind]: 0})
    MEDIA_CACHE_INVALIDATED.fire()
    return True


def _download_lutris(url, kind):
    parts = urlsplit(url)
    configured_host = urlsplit(settings.SITE_URL).hostname
    if (
        parts.scheme not in ("https", "http")
        or parts.hostname not in {configured_host, "lutris.net", "www.lutris.net", "images.igdb.com"}
        or parts.username
        or parts.password
        or parts.port not in (None, 80, 443)
    ):
        raise ValueError("Invalid artwork URL")
    if "\\" in url or any(ord(char) <= 32 for char in url) or ".." in unquote(parts.path).split("/"):
        raise ValueError("Invalid artwork URL")
    response = steamgriddb._Request(url).get()
    if response.status_code != 200:
        raise ValueError("Artwork download failed")
    return _decode(response.content, kind)


def _lutris_lookup(rows):
    from lutris.api import get_api_games

    slugs = {row["slug"] for row in rows if row.get("slug")}
    if not slugs:
        return {}
    result = {}
    for game in get_api_games(list(slugs)):
        urls = {
            "banner": game.get("banner_url") or game.get("banner"),
            "cover": game.get("coverart"),
            "icon": game.get("icon_url") or game.get("icon"),
        }
        result[game["slug"]] = {kind: url for kind, url in urls.items() if url}
        for alias in game.get("aliases", []):
            if alias.get("slug") in slugs:
                result.setdefault(alias["slug"], result[game["slug"]])
    return result


def _result(game, status, updated=()):
    return RefreshResult(status, tuple(updated), str(game["id"]), game.get("name") or "", game["_source"])


def _refresh_one(game, kinds, api, lutris_urls, *, reset=False):
    with ARTWORK_LOCK:
        if not _current(game):
            return _result(game, "stale")
    if game["_source"] == "steamgriddb":
        if api is None:
            return _result(game, "missing_key")
        lookup = steamgriddb.lookup_artwork(game.get("name") or "", api=api)
        with ARTWORK_LOCK:
            if not _current(game):
                return _result(game, "stale")
        if lookup.status != "success":
            return _result(game, lookup.status)
        if not kinds:
            return _result(game, "success")
        urls = lookup.urls
        download = steamgriddb.download_artwork
    else:
        urls = lutris_urls.get(game.get("slug"))
        if urls is None:
            return _result(game, "no_match")
        download = _download_lutris
    updated = []
    failed = stale = False
    for kind in kinds:
        with ARTWORK_LOCK:
            current = _current(game)
            if not current:
                stale = True
                break
            if bool(current.get(_FLAGS[kind])) != bool(game.get(_FLAGS[kind])) or (
                current.get(_FLAGS[kind]) and not reset
            ):
                stale = True
                continue
        if not urls.get(kind):
            continue
        try:
            data = download(urls[kind], kind)
            if not data:
                failed = True
            elif _publish(game, kind, data, reset=reset):
                updated.append(kind)
            else:
                stale = True
        except steamgriddb._StopBatch as error:
            error.updated_kinds = tuple(updated)
            raise
        except _ERRORS:
            failed = True
    return _result(game, "success" if updated else "stale" if stale else "error" if failed else "no_assets", updated)


def refresh_artwork(
    game_ids: Iterable[str] | None = None, *, force=False, inherited_only=False
) -> dict[str, RefreshResult]:
    """Refresh selected-source artwork, never replacing manually protected slots."""
    # One batch owns network work; callers never create per-game worker queues here.
    with _BATCH_LOCK:
        selected = {str(value) for value in game_ids} if game_ids is not None else None
        with ARTWORK_LOCK:
            rows = [
                dict(row, _source=get_effective_source(row))
                for row in games.get_games()
                if (selected is None or str(row["id"]) in selected)
                and (not inherited_only or row.get("artwork_source") is None)
            ]
        tasks = []
        results = {}
        for row in rows:
            kinds = [kind for kind, flag in _FLAGS.items() if not row.get(flag) and (force or not _fresh(row, kind))]
            if kinds or (force and row["_source"] == "steamgriddb"):
                tasks.append((row, kinds))
            else:
                results[str(row["id"])] = _result(row, "success")
        key = (
            settings.read_setting("steamgriddb_api_key")
            if any(row["_source"] == "steamgriddb" for row, _ in tasks)
            else None
        )
        api = steamgriddb._API(key.strip()) if isinstance(key, str) and key.strip() else None
        lutris_rows = [row for row, _ in tasks if row["_source"] == "lutris"]
        lutris_error = False
        try:
            lutris_urls = _lutris_lookup(lutris_rows) if lutris_rows else {}
        except _ERRORS:
            lutris_urls = {}
            lutris_error = True
        stopped = False
        for row, kinds in tasks:
            if (row["_source"] == "lutris" and lutris_error) or (row["_source"] == "steamgriddb" and stopped):
                result = _result(row, "error")
            else:
                try:
                    result = _refresh_one(row, kinds, api, lutris_urls)
                except steamgriddb._StopBatch as error:
                    stopped = True
                    updated = getattr(error, "updated_kinds", ())
                    result = _result(row, "success" if updated else "error", updated)
                except _ERRORS:
                    result = _result(row, "error")
            results[str(row["id"])] = result
        return results


def save_custom_artwork(game_id: str, kind: str, image_path: str) -> None:
    if kind not in _FILES:
        raise ValueError("Unknown artwork kind")
    path = Path(image_path)
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("Artwork file too large")
    data = _decode(path.read_bytes(), kind)
    with ARTWORK_LOCK:
        if not games.get_game_by_field(game_id, "id"):
            raise ValueError("Game no longer exists")
        _atomic_write(_path(game_id, kind, True), data)
        games.update_existing(id=game_id, **{_FLAGS[kind]: 1})
    MEDIA_CACHE_INVALIDATED.fire()


def reset_custom_artwork(game_id: str, kind: str) -> RefreshResult:
    if kind not in _FILES:
        raise ValueError("Unknown artwork kind")
    with _BATCH_LOCK:
        with ARTWORK_LOCK:
            row = games.get_game_by_field(game_id, "id")
            if not row:
                return RefreshResult("stale", (), str(game_id), "", "lutris")
            row = dict(row, _source=get_effective_source(row))
        key = settings.read_setting("steamgriddb_api_key") if row["_source"] == "steamgriddb" else None
        api = steamgriddb._API(key.strip()) if isinstance(key, str) and key.strip() else None
        try:
            urls = _lutris_lookup([row]) if row["_source"] == "lutris" else {}
            return _refresh_one(row, [kind], api, urls, reset=True)
        except _ERRORS + (steamgriddb._StopBatch,):
            return _result(row, "error")
