import os

from lutris import settings
from lutris.util.log import logger
from lutris.util.http import Request

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


def fetch_icons(game_slugs, callback=None, stop_request=None):
    no_banners = []
    no_icons = []
    for slug in game_slugs:
        if not has_icon(slug, BANNER):
            no_banners.append(slug)
        if not has_icon(slug, ICON):
            no_icons.append(slug)
    for game in no_banners:
        if stop_request and stop_request.is_set():
            break
        download_icon(slug, BANNER, callback=callback, stop_request=stop_request)
    for game in no_icons:
        if stop_request and stop_request.is_set():
            break
        download_icon(slug, ICON, callback=callback, stop_request=stop_request)


def download_icon(game_slug, icon_type, overwrite=False, callback=None,
                  stop_request=None):
    url = get_icon_url(game_slug, icon_type)
    dest = get_icon_path(game_slug, icon_type)

    if os.path.exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            return

    request = Request(url, stop_request=stop_request).get()
    content = request.content
    if content:
        with open(dest, 'wb') as dest_file:
            dest_file.write(content)
        if callback:
            logger.debug("Downloaded %s for %s" % (icon_type, game_slug))
            callback(game_slug)
