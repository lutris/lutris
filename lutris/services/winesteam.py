from lutris.services.steam import sync_with_lutris as _sync_with_lutris
from lutris.services.steam import load_games as _load_games

NAME = "Steam for Windows"
ICON = "winesteam"
ONLINE = False


def load_games():
    return _load_games(platform="windows")

def sync_with_lutris(games):
    return _sync_with_lutris(games, platform="windows")
