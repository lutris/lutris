"""Service package"""
import os

from lutris import settings
from lutris.services.battlenet import BattleNetService
from lutris.services.bethesda import BethesdaService
from lutris.services.dolphin import DolphinService
from lutris.services.egs import EpicGamesStoreService
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.itchio import ItchIoService
from lutris.services.lutris import LutrisService
from lutris.services.mame import MAMEService
from lutris.services.origin import OriginService
from lutris.services.steam import SteamService
from lutris.services.steamwindows import SteamWindowsService
from lutris.services.ubisoft import UbisoftConnectService
from lutris.services.xdg import XDGService
from lutris.util import system
from lutris.util.dolphin.cache_reader import DOLPHIN_GAME_CACHE_FILE
from lutris.util.linux import LINUX_SYSTEM

DEFAULT_SERVICES = ["lutris", "gog", "egs", "origin", "ubisoft", "steam"]


def get_services():
    """Return a mapping of available services"""
    _services = {
        "lutris": LutrisService,
        "gog": GOGService,
        "humblebundle": HumbleBundleService,
        "egs": EpicGamesStoreService,
        "origin": OriginService,
        "ubisoft": UbisoftConnectService,
    }
    if not LINUX_SYSTEM.is_flatpak:
        _services["xdg"] = XDGService
    if LINUX_SYSTEM.has_steam:
        _services["steam"] = SteamService
    _services["steamwindows"] = SteamWindowsService
    if system.path_exists(DOLPHIN_GAME_CACHE_FILE):
        _services["dolphin"] = DolphinService
    return _services


SERVICES = get_services()


# Those services are not yet ready to be used
WIP_SERVICES = {
    "battlenet": BattleNetService,
    "itchio": ItchIoService,
    "mame": MAMEService,
}

if os.environ.get("LUTRIS_ENABLE_ALL_SERVICES"):
    SERVICES.update(WIP_SERVICES)


def get_enabled_services():
    return {
        key: _class for key, _class in SERVICES.items()
        if settings.read_setting(key, section="services").lower() == "true"
    }
