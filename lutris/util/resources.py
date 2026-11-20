"""Utility module to handle media resources"""

import os

from lutris import settings


def _get_game_path(slot, legacy_path, game_id, game_data):
    if game_data is None and game_id is not None:
        from lutris.database import games

        game_data = games.get_game_by_field(game_id, "id")
    if not game_data:
        return legacy_path

    from lutris.artwork import get_game_media_paths
    from lutris.services.lutris import LutrisService
    from lutris.services.service_media import resolve_media_path

    media = LutrisService.medias[slot]()
    return resolve_media_path(get_game_media_paths(game_data, media)).path


def get_icon_path(game_slug: str, game_id=None, game_data=None) -> str:
    """Return the absolute path for a game_slug icon"""
    legacy = os.path.join(settings.ICON_PATH, "lutris_%s.png" % game_slug)
    return _get_game_path("icon", legacy, game_id, game_data)


def get_banner_path(game_slug: str, game_id=None, game_data=None) -> str:
    """Return the absolute path for a game_slug banner"""
    legacy = os.path.join(settings.BANNER_PATH, "{}.jpg".format(game_slug))
    return _get_game_path("banner", legacy, game_id, game_data)


def get_cover_path(game_slug: str, game_id=None, game_data=None) -> str:
    """Return the absolute path for a game_slug coverart"""
    legacy = os.path.join(settings.COVERART_PATH, "{}.jpg".format(game_slug))
    return _get_game_path("coverart_big", legacy, game_id, game_data)
