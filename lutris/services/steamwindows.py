from gettext import gettext as _
from lutris.services.steam import SteamService, SteamGame


class SteamWindowsGame(SteamGame):
    service = "steamwindows"
    installer_slug = "steamwindows"
    runner = "wine"


class SteamWindowsService(SteamService):
    id = "steamwindows"
    name = _("Steam for Windows")
    runner = "wine"
    game_class = SteamWindowsGame
