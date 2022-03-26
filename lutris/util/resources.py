"""Utility module to handle media resources"""
import os

from lutris import settings


def get_icon_path(game_slug):
    """Return the absolute path for a game_slug icon"""
    return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game_slug)


def get_banner_path(game_slug):
    """Return the absolute path for a game_slug banner"""
    return os.path.join(settings.BANNER_PATH, "%s.png" % game_slug)


def get_cover_path(game_slug):
    """Return the absolute path for a game_slug coverart"""
    return os.path.join(settings.COVERART_PATH, "%s.png" % game_slug)
