"""Utility module to handle media resources"""
import os

from lutris import settings


def get_icon_path(game_slug):
    """Return the absolute path for a game_slug icon"""
    return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game_slug)
