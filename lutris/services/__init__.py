"""Service package"""
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.steam import SteamService
from lutris.services.xdg import XDGService


class AuthenticationError(Exception):
    """Raised when authentication to a service fails"""


class UnavailableGame(Exception):
    """Raised when a game is available from a service"""


def get_services():
    """Return a list of active services"""
    return {
        "xdg": XDGService,
        "gog": GOGService,
        "humblebundle": HumbleBundleService,
        "steam": SteamService
    }
