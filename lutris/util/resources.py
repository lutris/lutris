"""Utility module to handle media resources"""

import os
import re

from lutris import settings


_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def _sanitize_game_slug(game_slug: str) -> str:
    if not _SLUG_RE.fullmatch(game_slug):
        raise ValueError("Invalid game slug")
    return game_slug


def _safe_join(base_path: str, filename: str) -> str:
    base_real = os.path.realpath(base_path)
    candidate_path = os.path.realpath(os.path.join(base_real, filename))
    if os.path.commonpath([base_real, candidate_path]) != base_real:
        raise ValueError("Invalid resource path")
    return candidate_path


def get_icon_path(game_slug: str) -> str:
    """Return the absolute path for a game_slug icon"""
    slug = _sanitize_game_slug(game_slug)
    return _safe_join(settings.ICON_PATH, "lutris_%s.png" % slug)


def get_banner_path(game_slug: str) -> str:
    """Return the absolute path for a game_slug banner"""
    slug = _sanitize_game_slug(game_slug)
    return _safe_join(settings.BANNER_PATH, "{}.jpg".format(slug))


def get_cover_path(game_slug: str) -> str:
    """Return the absolute path for a game_slug coverart"""
    slug = _sanitize_game_slug(game_slug)
    return _safe_join(settings.COVERART_PATH, "{}.jpg".format(slug))
