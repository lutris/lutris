"""EA Origin service.
Not ready yet.
"""
from gettext import gettext as _

from lutris.services.base import OnlineService


class OriginService(OnlineService):
    """Service class for EA Origin"""

    id = "origin"
    name = _("Origin")
    icon = "origin"
