from lutris.services.steam import SteamSyncer

NAME = "Steam for Windows"
ICON = "winesteam"
ONLINE = False


class WineSteamSyncer(SteamSyncer):
    platform = "windows"


SYNCER = WineSteamSyncer
