"""Utility module to handle media resources"""

import os
import re

from lutris import settings



def _normalize_game_slug(game_slug: str) -> str:
    game_slug = re.sub(r"[^a-z0-9_-]", "", game_slug.lower())
    if not game_slug:
        raise ValueError("Invalid game slug")
    return game_slug


def _get_media_path(base_path: str, filename: str) -> str:
    base_path = os.path.realpath(base_path)
    media_path = os.path.realpath(os.path.join(base_path, filename))
    if os.path.commonpath([base_path, media_path]) != base_path:
        raise ValueError("Invalid media path")
    return media_path


def get_icon_path(game_slug: str) -> str:
    """Return the absolute path for a game_slug icon"""
    game_slug = _normalize_game_slug(game_slug)
    return _get_media_path(settings.ICON_PATH, "lutris_%s.png" % game_slug)


def get_banner_path(game_slug: str) -> str:
    """Return the absolute path for a game_slug banner"""
    game_slug = _normalize_game_slug(game_slug)
    return _get_media_path(settings.BANNER_PATH, "{}.jpg".format(game_slug))


def get_cover_path(game_slug: str) -> str:
    """Return the absolute path for a game_slug coverart"""
    game_slug = _normalize_game_slug(game_slug)
    return _get_media_path(settings.COVERART_PATH, "{}.jpg".format(game_slug))
