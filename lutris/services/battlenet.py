"""Battle.net service.
Not ready yet.
"""
from gettext import gettext as _

from lutris.services.base import OnlineService


class BattleNetService(OnlineService):
    """Service class for Battle.net"""

    id = "battlenet"
    name = _("Battle.net")
    icon = "battlenet"
    medias = {}
