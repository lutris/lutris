"""Itch.io service.
Not ready yet.
"""
from gettext import gettext as _

from lutris.services.base import OnlineService


class ItchIoService(OnlineService):
    """Service class for Itch.io"""

    id = "itchio"
    name = _("Itch.io")
    icon = "itchio"
