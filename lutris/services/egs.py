"""Epic Games Store service.
Not ready yet.
"""
from gettext import gettext as _

from lutris.services.base import OnlineService


class EpicGamesStoreService(OnlineService):
    """Service class for Epic Games Store"""

    id = "egs"
    name = _("Epic Games Store")
    icon = "egs"
