"""Find a game's artwork at the store it came from.

Steam, Epic and GOG are asked directly for their full size art. Other services
use the largest portrait and landscape formats their own media classes know.
"""

import json
from dataclasses import dataclass
from typing import Any

import requests

from lutris.database.services import ServiceGameCollection
from lutris.util.http import get_request_proxies
from lutris.util.log import logger

STEAM_URL = "https://shared.steamstatic.com/store_item_assets/steam/apps/%s/%s"
GOG_GAMESDB_URL = "https://gamesdb.gog.com/platforms/gog/external_releases/%s"
TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class ArtworkUrls:
    """Candidate URLs for each kind of artwork, best first."""

    cover: tuple[str, ...] = ()
    banner: tuple[str, ...] = ()
    icon: tuple[str, ...] = ()


def _urls(*urls: str | None) -> tuple[str, ...]:
    return tuple(url for url in urls if url)


def store_artwork(service: str, appid: str) -> ArtworkUrls:
    """Return what the game's store offers; nothing for a game from no known store."""
    if not service or not appid:
        return ArtworkUrls()
    if service in ("steam", "steamwindows", "steamfamily"):
        # The 2x cover is the actual 600x900 one, and the header has a 920x430 grid's shape
        return ArtworkUrls(
            cover=_urls(STEAM_URL % (appid, "library_600x900_2x.jpg"), STEAM_URL % (appid, "library_600x900.jpg")),
            banner=_urls(STEAM_URL % (appid, "header.jpg")),
        )
    details = _service_details(service, appid)
    if service == "egs":
        return _egs_artwork(details)
    if service == "gog":
        return ArtworkUrls(cover=_urls(_gog_vertical_cover(appid)), banner=_urls(_gog_banner(details)))
    return _service_media_artwork(service, details)


def _service_details(service: str, appid: str) -> dict[str, Any]:
    try:
        game = ServiceGameCollection.get_game(service, appid)
    except ValueError:
        return {}
    if not game or not game.get("details"):
        return {}
    try:
        details = json.loads(str(game["details"]))
    except ValueError:
        return {}
    return details if isinstance(details, dict) else {}


def _egs_artwork(details: dict[str, Any]) -> ArtworkUrls:
    images = {image.get("type"): image.get("url") for image in details.get("keyImages", []) if isinstance(image, dict)}
    return ArtworkUrls(cover=_urls(images.get("DieselGameBoxTall")), banner=_urls(images.get("DieselGameBox")))


def _gog_vertical_cover(appid: str) -> str | None:
    """GOG Galaxy's own vertical cover, from GOG's public game database."""
    try:
        response = requests.get(
            GOG_GAMESDB_URL % appid, timeout=TIMEOUT_SECONDS, proxies=get_request_proxies(GOG_GAMESDB_URL)
        )
        if not response.ok:
            return None
        url_format = response.json().get("game", {}).get("vertical_cover", {}).get("url_format")
    except (requests.RequestException, ValueError, AttributeError) as error:
        logger.debug("No GOG cover for %s: %s", appid, error)
        return None
    if not isinstance(url_format, str):
        return None
    return url_format.replace("{formatter}", "_glx_vertical_cover").replace("{ext}", "jpg")


def _gog_banner(details: dict[str, Any]) -> str | None:
    image = details.get("image")
    return f"https:{image}_392.jpg" if isinstance(image, str) and image else None


def _service_media_artwork(service: str, details: dict[str, Any]) -> ArtworkUrls:
    # Imported here: the services sync artwork themselves, so they import this package
    from lutris.services import SERVICES

    service_class = SERVICES.get(service)
    if not service_class or not details:
        return ArtworkUrls()
    medias = [media() for media in {**service_class.medias, **service_class.extra_medias}.values()]
    portrait = [media for media in medias if media.size[1] > media.size[0]]
    landscape = [media for media in medias if media.size[0] > media.size[1]]
    return ArtworkUrls(cover=_urls(_largest_url(portrait, details)), banner=_urls(_largest_url(landscape, details)))


def _largest_url(medias: list[Any], details: dict[str, Any]) -> str | None:
    for media in sorted(medias, key=lambda media: media.size[0] * media.size[1], reverse=True):
        try:
            if url := media.get_media_url(details):
                return url
        except Exception as error:
            logger.debug("No %s artwork: %s", type(media).__name__, error)
    return None
