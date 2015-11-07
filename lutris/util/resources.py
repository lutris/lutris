import os

from lutris import settings
from lutris.util.log import logger
from lutris.util import http

BANNER = "banner"
ICON = "icon"


def get_icon_path(game, icon_type):
    if icon_type == BANNER:
        return os.path.join(settings.BANNER_PATH, "%s.jpg" % game)
    if icon_type == ICON:
        return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game)


def get_icon_url(game, icon_type):
    if icon_type == BANNER:
        return settings.BANNER_URL % game
    if icon_type == ICON:
        return settings.ICON_URL % game


def has_icon(game, icon_type):
    if icon_type == BANNER:
        icon_path = get_icon_path(game, BANNER)
        return os.path.exists(icon_path)
    elif icon_type == ICON:
        icon_path = get_icon_path(game, ICON)
        return os.path.exists(icon_path)


def fetch_icons(games, callback=None, stop_request=None):
    no_banners = []
    no_icons = []
    for game in games:
        if not has_icon(game['slug'], BANNER):
            no_banners.append(game)
        if not has_icon(game['slug'], ICON):
            no_icons.append(game)
    for game in no_banners:
        if stop_request and stop_request.is_set():
            break
        download_icon(game['slug'], BANNER, callback=callback,
                      stop_request=stop_request, game_id=game['id'])
    for game in no_icons:
        if stop_request and stop_request.is_set():
            break
        download_icon(game['slug'], ICON, callback=callback,
                      stop_request=stop_request, game_id=game['id'])


def download_icon(game_slug, icon_type, overwrite=False, callback=None,
                  stop_request=None, game_id=None):
    icon_url = get_icon_url(game_slug, icon_type)
    icon_path = get_icon_path(game_slug, icon_type)
    icon_downloaded = http.download_asset(icon_url, icon_path, overwrite,
                                          stop_request=stop_request)
    if icon_downloaded and callback:
        logger.debug("Downloaded %s for %s" % (icon_type, game_slug))
        callback(game_id)
