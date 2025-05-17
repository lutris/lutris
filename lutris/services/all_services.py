"""All services combined"""

from gettext import gettext as _

from lutris.services.base import BaseService, OnlineService
from lutris.services.steam import SteamBanner
from lutris.util.log import logger


class AllService(BaseService):
    """Class that aggregates all avaliable services on one tab"""

    id = "all_services"
    name = _("All services")
    icon = "lutris"
    medias = {"banner": SteamBanner}
    default_format = "banner"

    def load(self):
        """Return all importable games"""
        from lutris.services import get_enabled_services

        """Gets around circular import limitations. Do tell if you have a better way"""

        target_services = get_enabled_services()
        target_services.pop(self.id)
        total_game_list = []
        for service_name, service_class in target_services.items():
            logger.debug("Checking service %s with class %s", service_name, service_class)
            service_object = service_class()
            if isinstance(service_object, OnlineService):
                if service_object.is_authenticated():
                    logger.debug("Service %s is authenticated", service_name)
            elif isinstance(service_object, BaseService):
                total_game_list.append(service_object.load())
        return total_game_list
