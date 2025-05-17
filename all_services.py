"""All services combined"""

from lutris.services.base import BaseService


class AllService(BaseService):
    """Class that aggregates all avaliable services on one tab"""

    id = "all"
    name = _("All services")
    icon = "steam-client"

    def load(self):
        """Return all importable games"""
