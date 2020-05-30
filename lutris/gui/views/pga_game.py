"""Game representation for views"""
# Standard Library
import time

# Lutris Modules
from lutris import runners
from lutris.game import Game
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime, gtk_safe


class PgaGame:

    """Representation of a game for views
    TODO: Fix overlap with Game class
    """

    def __init__(self, pga_data):
        if not pga_data:
            raise RuntimeError("No game data provided")
        self._pga_data = pga_data
        self.runner_names = {runner: runners.import_runner(runner).human_name for runner in runners.__all__}

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<PgaGame id=%s slug=%s>" % (self.id, self.slug)

    @property
    def id(self):  # pylint: disable=invalid-name
        """Game internal ID"""
        return self._pga_data["id"]

    @property
    def slug(self):
        """Slug identifier"""
        return gtk_safe(self._pga_data["slug"])

    @property
    def name(self):
        """Name"""
        return gtk_safe(self._pga_data["name"])

    @property
    def year(self):
        """Year"""
        return str(self._pga_data["year"] or "")

    @property
    def runner(self):
        """Runner slug"""
        return gtk_safe(self._pga_data["runner"])

    @property
    def runner_text(self):
        """Runner name"""
        return gtk_safe(self.runner_names.get(self.runner))

    @property
    def platform(self):
        """Platform"""
        _platform = self._pga_data["platform"]
        if not _platform and self.installed:
            game_inst = Game(self._pga_data["id"])
            if game_inst.platform:
                _platform = game_inst.platform
            else:
                logger.debug("Game %s has no platform", self)
        return _platform

    @property
    def installed(self):
        """Game is installed"""
        if not self._pga_data["runner"]:
            return False
        return self._pga_data["installed"]

    def get_pixbuf(self, icon_type):
        """Pixbuf varying on icon type"""
        return get_pixbuf_for_game(self._pga_data["slug"], icon_type, self._pga_data["installed"])

    @property
    def installed_at(self):
        """Date of install"""
        return self._pga_data["installed_at"]

    @property
    def installed_at_text(self):
        """Date of install (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self._pga_data["installed_at"])) if self.
            _pga_data["installed_at"] else ""
        )

    @property
    def lastplayed(self):
        """Date of last play"""
        return self._pga_data["lastplayed"]

    @property
    def lastplayed_text(self):
        """Date of last play (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self._pga_data["lastplayed"])) if self._pga_data["lastplayed"] else ""
        )

    @property
    def playtime(self):
        """Playtime duration in hours"""
        return self._pga_data["playtime"] or 0.0

    @property
    def playtime_text(self):
        """Playtime duration in hours (textual representation)"""
        try:
            _playtime_text = get_formatted_playtime(self._pga_data["playtime"])
        except ValueError:
            logger.warning("Invalid playtime value %s for %s", self.playtime, self)
            _playtime_text = ""  # Do not show erroneous values
        return _playtime_text
