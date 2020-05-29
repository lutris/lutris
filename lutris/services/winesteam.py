"""Steam for Windows service"""
# Lutris Modules
from lutris.services.steam import SteamSyncer

NAME = "Steam for Windows"
ICON = "winesteam"
ONLINE = False


class WineSteamSyncer(SteamSyncer):

    """Sync games with Steam for Windows"""
    platform = "windows"


SYNCER = WineSteamSyncer
