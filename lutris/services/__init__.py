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
from lutris.services.ubisoft import UbisoftConnectService
from lutris.services.xdg import XDGService
from lutris.util import system
from lutris.util.dolphin.cache_reader import DOLPHIN_GAME_CACHE_FILE
from lutris.util.linux import LINUX_SYSTEM

DEFAULT_SERVICES = ["lutris", "gog", "humblebundle", "steam"]


def get_services():
    """Return a mapping of available services"""
    _services = {
        "lutris": LutrisService,
        "xdg": XDGService,
        "gog": GOGService,
        "humblebundle": HumbleBundleService,
    }
    if LINUX_SYSTEM.has_steam:
        _services["steam"] = SteamService
    if system.path_exists(DOLPHIN_GAME_CACHE_FILE):
        _services["dolphin"]: DolphinService
    return _services


SERVICES = get_services()


# Those services are not yet ready to be used
WIP_SERVICES = {
    "battlenet": BattleNetService,
    "bethesda": BethesdaService,
    "egs": EpicGamesStoreService,
    "itchio": ItchIoService,
    "mame": MAMEService,
    "origin": OriginService,
    "ubisoft": UbisoftConnectService,
}

if os.environ.get("LUTRIS_ENABLE_ALL_SERVICES"):
    SERVICES.update(WIP_SERVICES)


def get_enabled_services():
    return {
        key: _class for key, _class in SERVICES.items()
        if settings.read_setting(key, section="services").lower() == "true"
    }
