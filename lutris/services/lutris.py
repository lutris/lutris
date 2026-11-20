"""Artwork from Lutris.net, which needs no account."""

import os
from collections.abc import Iterable
from typing import Any

from lutris import settings
from lutris.api import get_api_games
from lutris.database.games import get_games
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisCoverartMedium, LutrisIcon
from lutris.services.service_media import download_media
from lutris.util import http
from lutris.util.log import logger


class LutrisMedia:
    """The artwork Lutris.net provides for games, by slug. It isn't a service: there's no
    account to log in to, only artwork anyone can download."""

    id = "lutris"
    medias = {
        "icon": LutrisIcon,
        "banner": LutrisBanner,
        "coverart_med": LutrisCoverartMedium,
        "coverart_big": LutrisCoverart,
    }
    default_format = "coverart_med"


def download_lutris_media(slug):
    """Download all media types for a single lutris game"""
    url = settings.SITE_URL + "/api/games/%s" % slug
    request = http.Request(url)
    try:
        response = request.get()
    except http.HTTPError as ex:
        logger.debug("Unable to load %s: %s", slug, ex)
        return
    response_data = response.json
    icon_url = _get_response_game_icon(response_data)
    if icon_url:
        download_media({slug: icon_url}, LutrisIcon())

    banner_url = _get_response_game_banner(response_data)
    if banner_url:
        download_media({slug: banner_url}, LutrisBanner())

    coverart_url = _get_response_game_coverart(response_data)
    if coverart_url:
        download_media({slug: coverart_url}, LutrisCoverart())


def sync_media(slugs: Iterable[str] | None = None) -> dict[str, int]:
    """Download missing media for Lutris games; if a set of slugs
    is not provided, downloads them for all games in the PGA."""
    if slugs is None:
        slugs = {game["slug"] for game in get_games()}
    else:
        slugs = set(s for s in slugs if s)

    if not slugs:
        return {}

    banners_available = {fn.split(".")[0] for fn in os.listdir(settings.BANNER_PATH)}
    icons_available = {
        fn.split(".")[0].replace("lutris_", "") for fn in os.listdir(settings.ICON_PATH) if fn.startswith("lutris_")
    }
    covers_available = {fn.split(".")[0] for fn in os.listdir(settings.COVERART_PATH)}
    complete_games = banners_available.intersection(icons_available).intersection(covers_available)

    slugs_to_download = slugs - complete_games
    if not slugs_to_download:
        return {}
    games = get_api_games(list(slugs_to_download))

    alias_map = {}
    api_slugs = set()
    for game in games:
        api_slugs.add(game["slug"])
        for alias in game["aliases"]:
            if alias["slug"] in slugs_to_download:
                alias_map[game["slug"]] = alias["slug"]
    alias_slugs = set(alias_map.values())
    used_alias_slugs = alias_slugs - api_slugs
    for alias_slug in used_alias_slugs:
        for game in games:
            if alias_slug in [alias["slug"] for alias in game["aliases"]]:
                game["slug"] = alias_map[game["slug"]]
                continue
    banner_urls = {
        game["slug"]: _get_response_game_banner(game)
        for game in games
        if game["slug"] not in banners_available and _get_response_game_banner(game)
    }
    icon_urls = {
        game["slug"]: _get_response_game_icon(game)
        for game in games
        if game["slug"] not in icons_available and _get_response_game_icon(game)
    }
    coverart_urls = {
        game["slug"]: _get_response_game_coverart(game)
        for game in games
        if game["slug"] not in covers_available and _get_response_game_coverart(game)
    }
    logger.debug("Syncing %s banners, %s icons and %s covers", len(banner_urls), len(icon_urls), len(coverart_urls))
    downloaded_banners = download_media(banner_urls, LutrisBanner())
    downloaded_icons = download_media(icon_urls, LutrisIcon())
    downloaded_covers = download_media(coverart_urls, LutrisCoverart())
    return {
        "banners": len(downloaded_banners),
        "icons": len(downloaded_icons),
        "covers": len(downloaded_covers),
    }


def _get_response_game_coverart(api_game: dict[str, Any]) -> str | None:
    return api_game.get("coverart")


def _get_response_game_banner(api_game: dict[str, Any]) -> str | None:
    return api_game.get("banner_url") or api_game.get("banner")


def _get_response_game_icon(api_game: dict[str, Any]) -> str | None:
    return api_game.get("icon_url") or api_game.get("icon")
