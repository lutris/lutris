"""Service package"""
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.steam import SteamService
from lutris.services.xdg import XDGService


def get_services():
    """Return a list of active services"""
    return {
        "xdg": XDGService,
        "gog": GOGService,
        "humblebundle": HumbleBundleService,
        "steam": SteamService
    }
