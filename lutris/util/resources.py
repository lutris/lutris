import os

from lutris import settings
from lutris.util.log import logger
from lutris.util import http


def get_banner_path(game):
    return os.path.join(settings.DATA_DIR, 'banners/%s.jpg' % game)


def has_banner(game_id):
    banner_path = get_banner_path(game_id)
    return os.path.exists(banner_path)


def fetch_banners(games, callback=None):
    no_banners = []
    logger.debug("Fetching icons")
    for game in games:
        if not has_banner(game):
            no_banners.append(game)
    for game in no_banners:
        download_banner(game, callback=callback)


def download_banner(game, overwrite=False, callback=None):
    banner_url = settings.INSTALLER_URL + '%s.jpg' % game
    banner_path = get_banner_path(game)
    cover_downloaded = http.download_asset(banner_url, banner_path, overwrite)
    if cover_downloaded and callback:
        logger.debug("Icon downloaded for %s", game)
        callback(game)
