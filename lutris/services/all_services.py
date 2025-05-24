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


def get_service_from_view(_view, game_id):
    selected_index = _view.get_selected_items()[0]
    selected_object = _view.game_store
    store_game_data = selected_object.store[selected_index]
    """With the game data + game_id we can find the service no?"""
    gotten_data = sql.filtered_query(
        settings.DB_PATH, "service_games", filters={"appid": game_id, "slug": store_game_data[1]}
    )
    target_service = gotten_data[0]["service"]
    """Gets around circular import limitations. Do tell if you have a better way"""
    from lutris.services import get_services

    target_service = get_services()[target_service]
    return target_service()
