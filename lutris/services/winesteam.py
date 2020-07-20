"""Steam for Windows service"""
from gettext import gettext as _

# Lutris Modules
from lutris.services.steam import SteamSyncer

NAME = _("Steam for Windows")
ICON = "winesteam"
ONLINE = False


class WineSteamSyncer(SteamSyncer):

    """Sync games with Steam for Windows"""
    platform = "windows"


SYNCER = WineSteamSyncer
