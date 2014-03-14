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
        return os.path.join(settings.ICON_PATH, "%s.png" % game)


def get_icon_url(game, icon_type):
    if icon_type == BANNER:
        return settings.INSTALLER_URL + '%s.jpg' % game
    if icon_type == ICON:
        return settings.INSTALLER_URL + 'icon/%s.png' % game


def has_icon(game, icon_type):
    if icon_type == BANNER:
        icon_path = get_icon_path(game, BANNER)
        return os.path.exists(icon_path)
    elif icon_type == ICON:
        icon_path = get_icon_path(game, ICON)
        return os.path.exists(icon_path)


def fetch_icons(games, callback=None):
    no_banners = []
    no_icons = []
    logger.debug("Fetching icons")
    for game in games:
        if not has_icon(game, BANNER):
            no_banners.append(game)
        if not has_icon(game, ICON):
            no_icons.append(game)
    for game in no_banners:
        download_icon(game, BANNER, callback=callback)
    for game in no_icons:
        download_icon(game, ICON, callback=callback)


def download_icon(game, icon_type, overwrite=False, callback=None):
    icon_url = get_icon_url(game, icon_type)
    icon_path = get_icon_path(game, icon_type)
    icon_downloaded = http.download_asset(icon_url, icon_path, overwrite)
    if icon_downloaded and callback:
        logger.debug("Downloaded %s for %s" % (icon_type, game))
        callback(game)
