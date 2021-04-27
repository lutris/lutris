"""Service package"""
from lutris import settings
from lutris.services.dolphin import DolphinService
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.lutris import LutrisService
from lutris.services.steam import SteamService
from lutris.services.xdg import XDGService

DEFAULT_SERVICES = ["lutris", "gog", "humblebundle", "steam"]


SERVICES = {
    "lutris": LutrisService,
    "gog": GOGService,
    "humblebundle": HumbleBundleService,
    "steam": SteamService,
    "dolphin": DolphinService,
    "xdg": XDGService,
}


def get_enabled_services():
    return {
        key: _class for key, _class in SERVICES.items()
        if settings.read_setting(key, section="services").lower() == "true"
    }
