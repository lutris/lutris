"""Bethesda service.
Not ready yet.
"""
from gettext import gettext as _

from lutris.services.base import OnlineService


class BethesdaService(OnlineService):
    """Service class for Battle.net"""

    id = "bethesda"
    name = _("Bethesda")
    icon = "bethesda"
