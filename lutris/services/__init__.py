from importlib import import_module

__all__ = ['steam', 'winesteam', 'xdg']


def get_services():
    mods = [import_module('lutris.services.%s' % name) for name in __all__]
    return mods
