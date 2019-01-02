from lutris.services.steam import sync_with_lutris as _sync_with_lutris

NAME = "Steam for Windows"
ICON = "winesteam"
ONLINE = True

def is_connected():
    # XXX
    return True

def sync_with_lutris(games):
    _sync_with_lutris(games, platform="windows")
