"""Service package"""
import os

from lutris.services.dolphin import DolphinService
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.lutris import LutrisService
from lutris.services.steam import SteamService


def get_services():
    """Return a list of active services"""
    enabled_services = {
        "lutris": LutrisService,
        "gog": GOGService,
        "humblebundle": HumbleBundleService,
        "steam": SteamService
    }
    if os.environ.get("LUTRIS_ENABLE_DOLPHIN"):
        enabled_services["dolphin"] = DolphinService
    return enabled_services
