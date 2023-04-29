"""Game representation for views"""
import time

from lutris.database import games
from lutris.database.games import get_service_games
from lutris.runners import get_runner_human_name
from lutris.services import SERVICES
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime, gtk_safe


class StoreItem:
    """Representation of a game for views
    TODO: Fix overlap with Game class
    """

    def __init__(self, game_data, service_media):
        if not game_data:
            raise RuntimeError("No game data provided")
        self._game_data = game_data
        self._cached_installed_game_data = None
        self.service_media = service_media

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Store id=%s slug=%s>" % (self.id, self.slug)

    @property
    def _installed_game_data(self):
        """Provides- and caches- the DB data for the installed game corresponding to this one,
        if it's a service game. We can get away with caching this because StoreItem instances are
        very short-lived, so the game won't be changed underneath us."""
        appid = self._game_data.get("appid")
        if appid:
            if self._cached_installed_game_data is None:
                self._cached_installed_game_data = games.get_game_for_service(self.service,
                                                                              self._game_data["appid"]) or {}
            return self._cached_installed_game_data

        return None

    def _get_game_attribute(self, key):
        value = self._game_data.get(key)

        if not value:
            game_data = self._installed_game_data

            if game_data:
                value = game_data.get(key)

        return value

    @property
    def id(self):  # pylint: disable=invalid-name
        """Game internal ID"""
        # Return an unique identifier for the game.
        # Since service games are not related to lutris, use the appid
        if "service_id" not in self._game_data:
            if "appid" in self._game_data:
                return self._game_data["appid"]
            return self._game_data["slug"]

        return self._game_data["id"]

    @property
    def service(self):
        return gtk_safe(self._game_data.get("service"))

    @property
    def slug(self):
        """Slug identifier"""
        return gtk_safe(self._game_data["slug"])

    @property
    def name(self):
        """Name"""
        return gtk_safe(self._game_data["name"])

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
    def installed(self):
        """Game is installed"""
        if "service_id" not in self._game_data:
            return self.id in get_service_games(self.service)
        if not self._game_data.get("runner"):
            return False
        return self._game_data.get("installed")

    def get_media_path(self):
        """Returns the path to the image file for this item"""
        if self._game_data.get("icon"):
            return self._game_data["icon"]

        return self.service_media.get_media_path(self.slug)

    @property
    def installed_at(self):
        """Date of install"""
        return self._get_game_attribute("installed_at")

    @property
    def installed_at_text(self):
        """Date of install (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self.installed_at)) if
            self.installed_at else ""
        )

    @property
    def lastplayed(self):
        """Date of last play"""
        return self._get_game_attribute("lastplayed")

    @property
    def lastplayed_text(self):
        """Date of last play (textual representation)"""
        return gtk_safe(
            time.strftime(
                "%X %x",
                time.localtime(self.lastplayed)
            ) if self.lastplayed else ""
        )

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
