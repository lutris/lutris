"""Game representation for views"""
import time

from lutris.game import Game
from lutris.gui.widgets.utils import get_pixbuf, get_pixbuf_for_game
from lutris.runners import RUNNER_NAMES
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime, gtk_safe


class StoreItem:
    """Representation of a game for views
    TODO: Fix overlap with Game class
    """

    def __init__(self, game_data):
        if not game_data:
            raise RuntimeError("No game data provided")
        self._game_data = game_data

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<GameItem id=%s slug=%s>" % (self.id, self.slug)

    @property
    def id(self):  # pylint: disable=invalid-name
        """Game internal ID"""
        # Return an unique identifier for the game.
        # Since service games are not related to lutris, use the appid
        if self._game_data.get("service"):
            return self._game_data["appid"]
        return self._game_data["id"]

    @property
    def slug(self):
        """Slug identifier (the lutris one)"""
        # The service slug is not useful to match with lutris games
        # Use the lutris slug instead.
        if self._game_data.get("service"):
            return self._game_data["lutris_slug"]
        return self._game_data["slug"]

    @property
    def name(self):
        """Name"""
        return gtk_safe(self._game_data["name"])

    @property
    def year(self):
        """Year"""
        return str(self._game_data["year"] or "")

    @property
    def runner(self):
        """Runner slug"""
        return gtk_safe(self._game_data["runner"])

    @property
    def runner_text(self):
        """Runner name"""
        return gtk_safe(RUNNER_NAMES.get(self.runner))

    @property
    def platform(self):
        """Platform"""
        _platform = self._game_data["platform"]
        if not _platform and self.installed:
            game_inst = Game(self._game_data["id"])
            if game_inst.platform:
                _platform = game_inst.platform
            else:
                logger.debug("Game %s has no platform", self)
        return _platform

    @property
    def installed(self):
        """Game is installed"""
        if not self._game_data["runner"]:
            return False
        return self._game_data["installed"]

    def get_pixbuf(self, icon_type):
        """Pixbuf varying on icon type"""
        if self._game_data.get("icon"):
            return get_pixbuf(self._game_data["icon"], (96, 96))
        return get_pixbuf_for_game(self._game_data["slug"], icon_type, self._game_data["installed"])

    @property
    def installed_at(self):
        """Date of install"""
        return self._game_data["installed_at"]

    @property
    def installed_at_text(self):
        """Date of install (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self._game_data["installed_at"])) if self.
            _game_data["installed_at"] else ""
        )

    @property
    def lastplayed(self):
        """Date of last play"""
        return self._game_data["lastplayed"]

    @property
    def lastplayed_text(self):
        """Date of last play (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self._game_data["lastplayed"])) if self._game_data["lastplayed"] else ""
        )

    @property
    def playtime(self):
        """Playtime duration in hours"""
        return self._game_data["playtime"] or 0.0

    @property
    def playtime_text(self):
        """Playtime duration in hours (textual representation)"""
        try:
            _playtime_text = get_formatted_playtime(self._game_data["playtime"])
        except ValueError:
            logger.warning("Invalid playtime value %s for %s", self.playtime, self)
            _playtime_text = ""  # Do not show erroneous values
        return _playtime_text
