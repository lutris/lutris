"""Artwork for library rows, resolved from Lutris and service caches."""

import asyncio
import os
import stat
from collections.abc import Iterable
from typing import Literal

from lutris import settings
from lutris.artwork import sync_artwork
from lutris.artwork.steamgriddb import API_KEY_ENVIRONMENT, API_KEY_PAGE, API_KEY_SETTING, SteamGridDB, get_api_key
from lutris.backend.models import ArtworkSettings, LibraryArtwork
from lutris.database.services import DBServiceGame, ServiceGameCollection
from lutris.services import SERVICES
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisIcon
from lutris.services.service_media import ServiceMedia

type ArtworkKind = Literal["cover", "banner", "icon"]


async def update_artwork() -> int:
    """Download the library's missing artwork and return the number of images downloaded."""
    return await asyncio.to_thread(sync_artwork)


async def get_artwork_settings() -> ArtworkSettings:
    return ArtworkSettings(
        steamgriddb_key_set=bool(get_api_key()),
        steamgriddb_key_from_environment=bool(os.environ.get(API_KEY_ENVIRONMENT)),
        steamgriddb_key_page=API_KEY_PAGE,
    )


async def set_steamgriddb_api_key(api_key: str) -> ArtworkSettings:
    """Check a SteamGridDB API key and save it, or forget the saved key when given none.
    Raises LutrisError if SteamGridDB refuses the key."""
    api_key = api_key.strip()
    if api_key:
        await asyncio.to_thread(SteamGridDB(api_key).check_api_key)
    settings.write_setting(API_KEY_SETTING, api_key)
    return await get_artwork_settings()


def _existing_image(path: str) -> str | None:
    if not path:
        return None
    path = os.path.expanduser(path)
    try:
        info = os.stat(path)
    except OSError, ValueError:
        return None
    return path if stat.S_ISREG(info.st_mode) and info.st_size else None


def _first_image(formats: Iterable[ServiceMedia], slug: str) -> str | None:
    if slug:
        for media in formats:
            for candidate in media.get_possible_media_paths(slug):
                if path := _existing_image(candidate.path):
                    return path
    return None


class ArtworkResolver:
    """Resolve one library query's artwork, loading each service catalog at most once."""

    def __init__(self) -> None:
        self._cover = LutrisCoverart()
        self._banner = LutrisBanner()
        self._icon = LutrisIcon()
        self._catalogs: dict[str, dict[str, DBServiceGame]] = {}
        self._formats: dict[str, dict[ArtworkKind, list[ServiceMedia]]] = {}

    def _service_formats(self, service: str) -> dict[ArtworkKind, list[ServiceMedia]]:
        if service not in self._formats:
            formats: dict[ArtworkKind, list[ServiceMedia]] = {"cover": [], "banner": [], "icon": []}
            media_types = SERVICES[service].medias.values()
            for media in sorted((media_type() for media_type in media_types), key=_image_area, reverse=True):
                width, height = media.size
                kind: ArtworkKind = "cover" if height > width else "banner" if width > height else "icon"
                formats[kind].append(media)
            self._formats[service] = formats
        return self._formats[service]

    def _catalog_game(self, service: str, appid: str) -> DBServiceGame | None:
        if service not in self._catalogs:
            self._catalogs[service] = {
                str(game["appid"]): game for game in ServiceGameCollection.get_for_service(service)
            }
        return self._catalogs[service].get(appid)

    def resolve(
        self,
        lutris_slug: str,
        service: str,
        service_id: str,
        service_slug: str,
        icon: str,
    ) -> LibraryArtwork:
        """Prefer Lutris artwork, then match artwork from the game's service."""
        cover = _first_image([self._cover], lutris_slug)
        banner = _first_image([self._banner], lutris_slug)
        custom_icon = _first_image([self._icon], lutris_slug)
        if cover and banner and custom_icon:
            return LibraryArtwork(cover, banner, custom_icon)

        if service in SERVICES:
            if not service_slug and service_id:
                catalog_game = self._catalog_game(service, service_id)
                if catalog_game:
                    service_slug = str(catalog_game.get("slug") or "")
                    icon = icon or str(catalog_game.get("icon") or "")
            if service_slug:
                formats = self._service_formats(service)
                cover = cover or _first_image(formats["cover"], service_slug)
                banner = banner or _first_image(formats["banner"], service_slug)
                custom_icon = custom_icon or _first_image(formats["icon"], service_slug)

        icon_path = _existing_image(icon) if os.path.isabs(os.path.expanduser(icon)) else None
        icon_name = icon if icon and "/" not in icon else None
        return LibraryArtwork(cover, banner, custom_icon or icon_path, icon_name)


def _image_area(media: ServiceMedia) -> int:
    width, height = media.size
    return width * height
