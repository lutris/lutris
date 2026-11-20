"""Fill in library games' missing covers, banners and icons.

Each game's store is asked first, then SteamGridDB, which also serves games that
come from no store. Downloads only fill in what's missing, so a user's custom
artwork is never replaced. Images no source has are remembered for a while, so
syncing the library doesn't ask again every time.
"""

import concurrent.futures
import json
import os
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import requests

from lutris import settings
from lutris.artwork.steamgriddb import BANNER_DIMENSIONS, COVER_DIMENSIONS, SteamGridDB, SteamGridDBError, get_api_key
from lutris.artwork.stores import ArtworkUrls, store_artwork
from lutris.database.games import get_games
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisIcon
from lutris.services.service_media import MEDIA_CACHE_INVALIDATED, ServiceMedia
from lutris.util.http import get_request_proxies
from lutris.util.log import logger

type ArtworkKind = Literal["cover", "banner", "icon"]

KINDS: tuple[ArtworkKind, ...] = ("cover", "banner", "icon")
STEAM_SERVICES = ("steam", "steamwindows", "steamfamily")
MISS_LIFETIME_SECONDS = 7 * 24 * 3600
MAX_WORKERS = 4
TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class ArtworkTarget:
    """A library game whose artwork is fetched: its slug names the files."""

    slug: str
    name: str
    service: str = ""
    service_id: str = ""


def _media(kind: ArtworkKind) -> ServiceMedia:
    return {"cover": LutrisCoverart, "banner": LutrisBanner, "icon": LutrisIcon}[kind]()


def has_artwork(kind: ArtworkKind, slug: str) -> bool:
    return any(path.exists for path in _media(kind).get_possible_media_paths(slug))


class _Misses:
    """What no source had, by slug, kind and whether SteamGridDB was asked."""

    def __init__(self) -> None:
        self._path = os.path.join(settings.CACHE_DIR, "artwork-misses.json")
        self._lock = threading.Lock()
        self._changed = False
        try:
            with open(self._path, encoding="utf-8") as misses_file:
                loaded = json.load(misses_file)
        except OSError, ValueError:
            loaded = {}
        now = time.time()
        self._misses: dict[str, float] = {
            key: when
            for key, when in (loaded.items() if isinstance(loaded, dict) else ())
            if isinstance(when, (int, float)) and now - when < MISS_LIFETIME_SECONDS
        }

    @staticmethod
    def _key(slug: str, kind: ArtworkKind, with_steamgriddb: bool) -> str:
        return f"{slug}:{kind}:{'steamgriddb' if with_steamgriddb else 'store'}"

    def recent(self, slug: str, kind: ArtworkKind, with_steamgriddb: bool) -> bool:
        with self._lock:
            return self._key(slug, kind, with_steamgriddb) in self._misses

    def record(self, slug: str, kind: ArtworkKind, with_steamgriddb: bool) -> None:
        with self._lock:
            self._misses[self._key(slug, kind, with_steamgriddb)] = time.time()
            self._changed = True

    def save(self) -> None:
        if not self._changed:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as misses_file:
                json.dump(self._misses, misses_file)
        except OSError as error:
            logger.warning("Could not save the artwork misses: %s", error)


def _image_extension(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return None


def _download(url: str, kind: ArtworkKind, slug: str) -> bool:
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS, proxies=get_request_proxies(url))
    except requests.RequestException as error:
        logger.debug("Could not download %s: %s", url, error)
        return False
    extension = _image_extension(response.content) if response.ok else None
    if not extension or (kind == "icon" and extension != ".png"):
        logger.debug("No usable %s image at %s (status %s)", kind, url, response.status_code)
        return False
    folder = str(_media(kind).dest_path)
    filename = f"lutris_{slug}.png" if kind == "icon" else f"{slug}{extension}"
    destination = os.path.join(folder, filename)
    os.makedirs(folder, exist_ok=True)
    temporary = destination + ".tmp"
    with open(temporary, "wb") as image_file:
        image_file.write(response.content)
    os.replace(temporary, destination)
    logger.debug("Saved the %s of %s from %s", kind, slug, url)
    return True


class _Fetcher:
    def __init__(self) -> None:
        api_key = get_api_key()
        self._steamgriddb: SteamGridDB | None = SteamGridDB(api_key) if api_key else None
        self._misses = _Misses()

    @property
    def uses_steamgriddb(self) -> bool:
        return self._steamgriddb is not None

    def fetch(self, target: ArtworkTarget) -> int:
        with_steamgriddb = self.uses_steamgriddb
        missing = [
            kind
            for kind in KINDS
            if not has_artwork(kind, target.slug) and not self._misses.recent(target.slug, kind, with_steamgriddb)
        ]
        if not missing:
            return 0

        urls = store_artwork(target.service, target.service_id) if target.service else ArtworkUrls()
        downloaded = 0
        remaining: list[ArtworkKind] = []
        for kind in missing:
            if any(_download(url, kind, target.slug) for url in getattr(urls, kind)):
                downloaded += 1
            else:
                remaining.append(kind)

        if remaining and self._steamgriddb:
            try:
                downloaded += self._fetch_from_steamgriddb(self._steamgriddb, target, remaining)
            except SteamGridDBError as error:
                # Without a working key, misses aren't recorded as SteamGridDB's
                logger.warning("SteamGridDB artwork for %s: %s", target.name, error)
                if "API key" in error.message:
                    self._steamgriddb = None
                return downloaded

        for kind in remaining:
            if not has_artwork(kind, target.slug):
                self._misses.record(target.slug, kind, with_steamgriddb)
        return downloaded

    def _fetch_from_steamgriddb(self, client: SteamGridDB, target: ArtworkTarget, kinds: list[ArtworkKind]) -> int:
        steam_appid = target.service_id if target.service in STEAM_SERVICES else ""
        game_id = client.find_game(target.name, steam_appid)
        if game_id is None:
            return 0
        downloaded = 0
        for kind in kinds:
            if kind == "icon":
                url = client.icon_url(game_id)
            else:
                url = client.grid_url(game_id, COVER_DIMENSIONS if kind == "cover" else BANNER_DIMENSIONS)
            if url and _download(url, kind, target.slug):
                downloaded += 1
        return downloaded

    def save(self) -> None:
        self._misses.save()


def library_targets(slugs: Iterable[str] | None = None) -> list[ArtworkTarget]:
    """Return a target for each slug in the library, or for every game; a game from a
    store is preferred when several games share a slug."""
    wanted = {slug for slug in slugs if slug} if slugs is not None else None
    targets: dict[str, ArtworkTarget] = {}
    for row in get_games():
        slug = row.get("slug") or ""
        if not slug or (wanted is not None and slug not in wanted):
            continue
        target = ArtworkTarget(
            slug=slug,
            name=row.get("name") or slug,
            service=row.get("service") or "",
            service_id=str(row.get("service_id") or ""),
        )
        if slug not in targets or (target.service and not targets[slug].service):
            targets[slug] = target
    return list(targets.values())


def fetch_artwork(targets: Iterable[ArtworkTarget]) -> int:
    """Download the missing artwork of some games; returns how many images were saved."""
    fetcher = _Fetcher()
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for future in concurrent.futures.as_completed(executor.submit(fetcher.fetch, target) for target in targets):
            try:
                total += future.result()
            except Exception as error:
                logger.exception("Artwork download failed: %s", error)
    fetcher.save()
    if total:
        MEDIA_CACHE_INVALIDATED.fire()
    return total


def sync_artwork(slugs: Iterable[str] | None = None) -> int:
    """Download the missing artwork of the library's games, or of those with these slugs."""
    return fetch_artwork(library_targets(slugs))


def fetch_game_artwork(slug: str) -> int:
    """Download the missing artwork of the library's game with this slug."""
    return sync_artwork([slug])
