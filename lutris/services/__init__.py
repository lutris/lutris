from importlib import import_module
from lutris.settings import read_setting


__all__ = ['steam', 'winesteam', 'xdg', 'scummvm', 'gog','rom']


class AuthenticationError(Exception):
    pass

def import_service(name):
    return import_module('lutris.services.%s' % name)


def get_services():
    return [import_service(name) for name in __all__]


def get_services_synced_at_startup():
    return [
        import_service(name)
        for name in __all__
        if read_setting('sync_at_startup', name) == 'True'
    ]
