"""Service package"""

import os

from lutris import settings
from lutris.services.amazon import AmazonService
from lutris.services.battlenet import BNET_ENABLED, BattleNetService
from lutris.services.dolphin import DolphinService
from lutris.services.ea_app import EAAppService
from lutris.services.egs import EpicGamesStoreService
from lutris.services.flathub import FlathubService
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.itchio import ItchIoService
from lutris.services.lutris import LutrisService
from lutris.services.mame import MAMEService
from lutris.services.scummvm import SCUMMVM_CONFIG_FILE, ScummvmService
from lutris.services.steam import SteamService
from lutris.services.steamfamily import SteamFamilyService
from lutris.services.steamwindows import SteamWindowsService
from lutris.services.ubisoft import UbisoftConnectService
from lutris.services.xdg import XDGService
from lutris.util import system
from lutris.util.dolphin.cache_reader import DOLPHIN_GAME_CACHE_FILE
from lutris.util.linux import LINUX_SYSTEM

DEFAULT_SERVICES = ["gog", "egs", "ea_app", "ubisoft", "steam"]


def get_services():
    """Return a mapping of available services"""
    _services = {
        "gog": GOGService,
        "humblebundle": HumbleBundleService,
        "egs": EpicGamesStoreService,
        "itchio": ItchIoService,
        "ea_app": EAAppService,
        "ubisoft": UbisoftConnectService,
        "amazon": AmazonService,
        "flathub": FlathubService,
    }
    if BNET_ENABLED:
        _services["battlenet"] = BattleNetService
    if not LINUX_SYSTEM.is_flatpak():
        _services["xdg"] = XDGService
    if LINUX_SYSTEM.has_steam():
        _services["steam"] = SteamService
    _services["steamwindows"] = SteamWindowsService
    _services["steamfamily"] = SteamFamilyService
    if system.path_exists(DOLPHIN_GAME_CACHE_FILE):
        _services["dolphin"] = DolphinService
    if system.path_exists(SCUMMVM_CONFIG_FILE):
        _services["scummvm"] = ScummvmService
    if os.environ.get("LUTRIS_SERVICE_ENABLED") == "1":
        _services["lutris"] = LutrisService
    return _services


SERVICES = get_services()


# Those services are not yet ready to be used
WIP_SERVICES = {
    "mame": MAMEService,
}

if os.environ.get("LUTRIS_ENABLE_ALL_SERVICES"):
    SERVICES.update(WIP_SERVICES)


def get_enabled_services():
    return {
        key: _class
        for key, _class in SERVICES.items()
        if settings.read_setting(key, section="services").lower() == "true"
    }
