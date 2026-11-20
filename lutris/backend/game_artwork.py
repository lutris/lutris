"""A game's own artwork: choosing, replacing and resetting its cover, banner and icon.

Images arrive as PNG or JPEG files the frontend prepared (it scales and converts
what the user picked) or as URLs, such as SteamGridDB's choices. Artwork the user
chose is marked custom and kept until reset, which goes back to the automatic
artwork from the game's store or SteamGridDB.
"""

import asyncio
from gettext import gettext as _
from typing import Literal, cast

import requests

from lutris import settings
from lutris.artwork.fetcher import artwork_path, fetch_game_artwork, forget_misses, remove_artwork, save_image
from lutris.artwork.steamgriddb import BANNER_DIMENSIONS, COVER_DIMENSIONS, SteamGridDB, get_api_key
from lutris.backend.models import ArtworkChoice, GameArtworkImage
from lutris.database import games as games_db
from lutris.database import sql
from lutris.exceptions import LutrisError
from lutris.services.service_media import MEDIA_CACHE_INVALIDATED
from lutris.util import system
from lutris.util.http import get_request_proxies

type ArtworkKind = Literal["cover", "banner", "icon"]

_CUSTOM_FLAGS: dict[str, str] = {
    "cover": "has_custom_coverart_big",
    "banner": "has_custom_banner",
    "icon": "has_custom_icon",
}
TIMEOUT_SECONDS = 30
# The most SteamGridDB choices offered at once
CHOICE_LIMIT = 48


def _game(game_id: str) -> games_db.DbGameDict:
    row = games_db.get_game_by_field(game_id, "id")
    if row is None:
        raise LutrisError(_("This game is no longer in the library."))
    if not row.get("slug"):
        raise LutrisError(_("This game has no identifier to store artwork under."))
    return row


def _kind(kind: str) -> ArtworkKind:
    if kind not in _CUSTOM_FLAGS:
        raise LutrisError(_("Unknown kind of artwork: %s") % kind)
    return cast(ArtworkKind, kind)


def _image(row: games_db.DbGameDict, kind: ArtworkKind) -> GameArtworkImage:
    return GameArtworkImage(kind=kind, path=artwork_path(kind, row["slug"]), custom=bool(row.get(_CUSTOM_FLAGS[kind])))


def _set_custom(game_id: str, kind: ArtworkKind, custom: bool) -> None:
    sql.db_update(settings.DB_PATH, "games", {_CUSTOM_FLAGS[kind]: int(custom)}, {"id": game_id})


def _announce(kind: ArtworkKind) -> None:
    if kind == "icon":
        system.update_desktop_icons()
    MEDIA_CACHE_INVALIDATED.fire()


async def get_game_artwork(game_id: str) -> tuple[GameArtworkImage, ...]:
    row = _game(game_id)
    return tuple(_image(row, kind) for kind in ("cover", "banner", "icon"))


def _store(game_id: str, kind: ArtworkKind, content: bytes) -> GameArtworkImage:
    row = _game(game_id)
    try:
        save_image(kind, row["slug"], content)
    except ValueError as error:
        message = _("Icons must be PNG images.") if kind == "icon" else _("Artwork must be a PNG or JPEG image.")
        raise LutrisError(message) from error
    _set_custom(game_id, kind, True)
    _announce(kind)
    return _image(_game(game_id), kind)


async def set_custom_artwork(game_id: str, kind: str, image_path: str) -> GameArtworkImage:
    """Use a PNG or JPEG file (PNG for icons) as a game's artwork until it's reset."""
    checked = _kind(kind)

    def read() -> bytes:
        try:
            with open(image_path, "rb") as image_file:
                return image_file.read()
        except OSError as error:
            raise LutrisError(_("The image could not be read: %s") % error) from error

    content = await asyncio.to_thread(read)
    return await asyncio.to_thread(_store, game_id, checked, content)


async def use_artwork_url(game_id: str, kind: str, url: str) -> GameArtworkImage:
    """Download an image, such as one of SteamGridDB's, as a game's artwork."""
    checked = _kind(kind)

    def download() -> bytes:
        try:
            response = requests.get(url, timeout=TIMEOUT_SECONDS, proxies=get_request_proxies(url))
            response.raise_for_status()
        except requests.RequestException as error:
            raise LutrisError(_("The image could not be downloaded: %s") % error) from error
        return response.content

    content = await asyncio.to_thread(download)
    return await asyncio.to_thread(_store, game_id, checked, content)


async def reset_artwork(game_id: str, kind: str) -> GameArtworkImage:
    """Drop a game's artwork of this kind and fetch the automatic one again."""
    checked = _kind(kind)
    row = _game(game_id)

    def reset() -> GameArtworkImage:
        remove_artwork(checked, row["slug"])
        _set_custom(game_id, checked, False)
        forget_misses(row["slug"])
        fetch_game_artwork(row["slug"])
        _announce(checked)
        return _image(_game(game_id), checked)

    return await asyncio.to_thread(reset)


async def list_steamgriddb_artwork(game_id: str, kind: str) -> tuple[ArtworkChoice, ...]:
    """Return SteamGridDB's images of this kind for a game, if a key is set."""
    checked = _kind(kind)
    row = _game(game_id)
    api_key = get_api_key()
    if not api_key:
        raise LutrisError(_("Set a SteamGridDB API key in View → Artwork Sources to choose from its artwork."))

    def search() -> tuple[ArtworkChoice, ...]:
        client = SteamGridDB(api_key)
        steam_appid = str(row.get("service_id") or "") if row.get("service") in ("steam", "steamwindows") else ""
        sgdb_id = client.find_game(row.get("name") or row["slug"], steam_appid)
        if sgdb_id is None:
            return ()
        if checked == "icon":
            images = client.icons(sgdb_id)
        else:
            sizes = COVER_DIMENSIONS if checked == "cover" else BANNER_DIMENSIONS
            images = [image for dimensions in sizes for image in client.grids(sgdb_id, dimensions)]
        return tuple(
            ArtworkChoice(
                url=str(image["url"]),
                thumbnail_url=str(image.get("thumb") or image["url"]),
                width=int(image.get("width") or 0),
                height=int(image.get("height") or 0),
            )
            for image in images[:CHOICE_LIMIT]
        )

    return await asyncio.to_thread(search)
