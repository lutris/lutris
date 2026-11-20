"""The library's own artwork formats, which lutris.artwork fills in."""

from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisCoverartMedium, LutrisIcon


class LutrisMedia:
    """The library's artwork for games, by slug, for views that pick their formats
    from a service. It isn't one: lutris.artwork downloads it from each game's store."""

    id = "lutris"
    medias = {
        "icon": LutrisIcon,
        "banner": LutrisBanner,
        "coverart_med": LutrisCoverartMedium,
        "coverart_big": LutrisCoverart,
    }
    default_format = "coverart_med"
