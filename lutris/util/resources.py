import os

from lutris import settings
from lutris.util import http


def get_banner_path(game):
    return os.path.join(settings.DATA_DIR, 'banners/%s.jpg' % game)


def has_banner(game_id):
    banner_path = get_banner_path(game_id)
    return os.path.exists(banner_path)


def fetch_banners(games):
    no_banners = []
    for game in games:
        if has_banner(game):
            print "{} OK".format(game)
        else:
            no_banners.append(game)
    for game in no_banners:
        download_banner(game)


def download_banner(game, overwrite=False):
    banner_url = settings.INSTALLER_URL + '%s.jpg' % game
    http.download_asset(banner_url, get_banner_path(game), overwrite)
