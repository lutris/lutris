"""TOSEC service
Not ready yet"""
from __future__ import annotations

from gettext import gettext as _

from lutris.services.base import BaseService


class TOSECService(BaseService):
    """Service class for TOSEC"""
    id = "tosec"
    name = _("TOSEC")
    icon = "tosec"
