import os
from lutris import settings


def get_banner_path(game_id):
    return os.path.join(settings.DATA_DIR, 'banners/%s.jpg' % game_id)


def has_banner(game_id):
    banner_path = get_banner_path(game_id)
    return os.path.exists(banner_path)
