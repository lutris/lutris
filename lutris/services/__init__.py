"""Service package"""
from importlib import import_module
from lutris.settings import read_setting


__all__ = ["xdg", "gog", "steam", "winesteam"]


class AuthenticationError(Exception):
    """Raised when authentication to a service fails"""


def import_service(name):
    """return a runner module by name"""
    return import_module("lutris.services.%s" % name)


def get_services():
    """Return a list of active services"""
    return [import_service(name) for name in __all__]


def get_services_synced_at_startup():
    """Return services synced at startup"""
    return [
        import_service(name)
        for name in __all__
        if read_setting("sync_at_startup", name) == "True"
    ]
