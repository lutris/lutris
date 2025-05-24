"""All services combined"""

from gettext import gettext as _

import lutris.database.sql as sql
from lutris import settings
from lutris.services.base import BaseService
from lutris.services.steam import SteamBanner
from lutris.util.log import logger


class AllService(BaseService):
    """Class that aggregates all avaliable services on one tab"""

    id = "all_services"
    name = _("All services")
    medias = {
        "banner": SteamBanner,
    }
    icon = "lutris"
    default_format = "banner"

    def install_by_id(self, appid):
        test_query = sql.filtered_query(settings.DB_PATH, "games", {"service_id": appid})
        logger.debug(test_query)
        return super().install_by_id(appid)

    def load(self):
        """Return all importable games"""
        from lutris.services import get_enabled_services

        """Gets around circular import limitations. Do tell if you have a better way"""
        test = get_enabled_services()
