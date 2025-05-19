"""All services combined"""

from gettext import gettext as _

from lutris.services.base import BaseService
from lutris.services.steam import SteamBanner


class AllService(BaseService):
    """Class that aggregates all avaliable services on one tab"""

    id = "all_services"
    name = _("All services")
    media = {
        "banner": SteamBanner,
    }
    icon = "lutris"
    default_format = "banner"

    def load(self):
        """Return all importable games"""
        from lutris.services import get_enabled_services

        """Gets around circular import limitations. Do tell if you have a better way"""
        test = get_enabled_services()
