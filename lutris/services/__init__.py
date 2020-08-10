"""Service package"""
from importlib import import_module

__all__ = ["xdg", "gog", "humblebundle", "steam"]


class AuthenticationError(Exception):
    """Raised when authentication to a service fails"""


class UnavailableGame(Exception):
    """Raised when a game is available from a service"""


def import_service(name):
    """return a runner module by name"""
    return import_module("lutris.services.%s" % name)


def get_services():
    """Return a list of active services"""
    return [import_service(name) for name in __all__]
