"""Game representation for views"""

import time
from typing import List

from lutris.database import games
from lutris.database.services import ServiceGameCollection
from lutris.runners import get_runner_human_name
from lutris.services import SERVICES, LutrisService
from lutris.services.service_media import MediaPath
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime, gtk_safe


class StoreItem:
    """Representation of a game for views
    TODO: Fix overlap with Game class
    """

    def __init__(self, game_data, service, service_media):
        if not game_data:
            raise RuntimeError("No game data provided")
        self._game_data = game_data
        self._cached_installed_game_data = None
        self._cached_installed_game_data_loaded = False
        self._service_obj = service
        self._service_media = service_media

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Store id=%s slug=%s>" % (self.id, self.slug)

    @property
    def _installed_game_data(self):
        """Provides- and caches- the DB data for the installed game corresponding to this one,
        if it's a service game. We can get away with caching this because StoreItem instances are
        very short-lived, so the game won't be changed underneath us."""
        if not self._cached_installed_game_data_loaded:
            appid = self._game_data.get("appid")
            service_id = self._game_data.get("service")
            if appid and service_id:
                self._cached_installed_game_data = games.get_game_for_service(service_id, appid) or {}
                self._cached_installed_game_data_loaded = True

        return self._cached_installed_game_data

    def apply_installed_game_data(self, installed_game_data):
        self._cached_installed_game_data_loaded = True
        self._cached_installed_game_data = installed_game_data

    def _get_game_attribute(self, key):
        if key in self._game_data:
            return self._game_data[key]

        installed_game_data = self._installed_game_data

        if installed_game_data:
            return installed_game_data.get(key)

        return None

    @property
    def id(self) -> str:  # pylint: disable=invalid-name
        """Game internal ID"""
        # Return a unique identifier for the game.
        # Since service games are not related to lutris, use the appid
        if "service_id" not in self._game_data:
            if "appid" in self._game_data:
                _id = self._game_data["appid"]
            else:
                _id = self._game_data["slug"]
        else:
            _id = self._game_data["id"]

        if not _id:
            logger.error("No id could be found for '%s'", self.name)

        return str(_id)

    @property
    def service(self):
        return gtk_safe(self._game_data.get("service"))

    @property
    def service_media(self):
        return self._service_media

    @property
    def slug(self):
        """Slug identifier"""
        return gtk_safe(self._game_data["slug"])

    @property
    def name(self):
        """Name"""
        return gtk_safe(self._game_data["name"])

    @property
    def sortname(self):
        """Name used for sorting"""
        return gtk_safe(self._get_game_attribute("sortname") or "")

    @property
    def year(self):
        """Year"""
        return str(self._get_game_attribute("year") or "")

    @property
    def runner(self):
        """Runner slug"""
        _runner = self._get_game_attribute("runner")
        return gtk_safe(_runner) or ""

    @property
    def runner_text(self):
        """Runner name"""
        return gtk_safe(get_runner_human_name(self.runner))

    @property
    def platform(self):
        """Platform"""
        _platform = self._get_game_attribute("platform")

        if not _platform and self.service in SERVICES:
            service = SERVICES[self.service]()
            _platforms = service.get_game_platforms(self._game_data)
            if _platforms:
                _platform = ", ".join(_platforms)

        return gtk_safe(_platform)

    @property
    def installed(self) -> bool:
        """Game is installed"""

        def check_data(data):
            return bool(data and data.get("installed") and data.get("runner"))

        if "installed" in self._game_data:
            return check_data(self._game_data)

        return check_data(self._installed_game_data)

    def get_media_paths(self) -> List[MediaPath]:
        """Returns the path to the image file for this item"""
        if self._game_data.get("icon"):
            return [self._game_data["icon"]]

        possible_paths = self.service_media.get_possible_media_paths(self.slug)
        media_paths = [mp for mp in possible_paths if mp.exists]
        if media_paths:
            return media_paths

        service = self._service_obj or LutrisService
        services = [(service, lambda: self.slug)]

        game_service_name = self._game_data.get("service")
        game_service_id = self._game_data.get("service_id")

        if game_service_name and game_service_id and game_service_name in SERVICES:

            def get_service_slug():
                service_game = ServiceGameCollection.get_game(game_service_name, game_service_id)
                return service_game.get("slug") if service_game else None

            game_service = SERVICES[game_service_name]()
            services.append((game_service, get_service_slug))

        fallback_path = self.service_media.get_fallback_media_path(services)
        return [fallback_path] if fallback_path else possible_paths

    @property
    def installed_at(self):
        """Date of install"""
        return self._get_game_attribute("installed_at")

    @property
    def installed_at_text(self):
        """Date of install (textual representation)"""
        return gtk_safe(time.strftime("%X %x", time.localtime(self.installed_at)) if self.installed_at else "")

    @property
    def lastplayed(self):
        """Date of last play"""
        return self._get_game_attribute("lastplayed")

    @property
    def lastplayed_text(self):
        """Date of last play (textual representation)"""
        return gtk_safe(time.strftime("%X %x", time.localtime(self.lastplayed)) if self.lastplayed else "")

    @property
    def playtime(self):
        """Playtime duration in hours"""
        try:
            return float(self._get_game_attribute("playtime") or 0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def playtime_text(self):
        """Playtime duration in hours (textual representation)"""
        try:
            _playtime_text = get_formatted_playtime(self.playtime)
        except ValueError:
            logger.warning("Invalid playtime value %s for %s", self.playtime, self)
            _playtime_text = ""  # Do not show erroneous values
        return gtk_safe(_playtime_text)
