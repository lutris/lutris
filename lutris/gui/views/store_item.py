"""Game representation for views"""

import time
from typing import TYPE_CHECKING

from lutris.database.services import ServiceGameCollection
from lutris.services import SERVICES
from lutris.services.lutris import LutrisMedia
from lutris.services.service_media import MediaPath
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime, gtk_safe

if TYPE_CHECKING:
    from lutris.backend.models import LibraryGame

# How far ahead of the current clock a timestamp may be before we stop believing it.
# A day absorbs ordinary clock skew and time zone confusion.
TIMESTAMP_FUTURE_TOLERANCE = 86400

# Bad timestamps already reported, as (game, field) pairs. The store is rebuilt on every
# search keystroke and each rebuild reads these fields twice (once for the value, once for
# the text), so without this the log fills with repeats of the same problem.
_reported_bad_timestamps = set()


def _describe_timestamp(value):
    """Render a timestamp for a log message, decoding it to a date where possible."""
    try:
        return "%s (%s)" % (value, time.strftime("%x", time.localtime(int(value))))
    except TypeError, ValueError, OSError, OverflowError:
        return repr(value)


def _report_bad_timestamp(game_name, field, value):
    """Warn that a timestamp was discarded, once per game and field."""
    key = (game_name, field)
    if key in _reported_bad_timestamps:
        return
    _reported_bad_timestamps.add(key)
    logger.warning(
        "Ignoring implausible %s for '%s': %s. This usually means the system clock was wrong "
        "when it was recorded; the date stays blank until the game is installed or played again.",
        field,
        game_name,
        _describe_timestamp(value),
    )


def sanitize_timestamp(value):
    """Return value as a plausible timestamp for a past event, or None if it isn't one.

    Install and last-played times can only describe something that already happened, so a
    value in the future means the clock was wrong when it was recorded rather than that the
    game will be installed later. Devices without a battery-backed RTC come up with a wildly
    wrong time, and anything installed or launched before NTP catches up gets stamped with it.

    This compares against the current time; it is not a check on how wide a timestamp may be.
    """
    try:
        timestamp = int(value)
    except TypeError, ValueError:
        return None
    if timestamp <= 0 or timestamp > time.time() + TIMESTAMP_FUTURE_TOLERANCE:
        return None
    return timestamp


class StoreItem:
    """Representation of a game for views: a row from the backend's library query,
    as the views display it."""

    def __init__(self, library_game: "LibraryGame", service, service_media):
        self._game = library_game
        self._service_obj = service
        self._service_media = service_media

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Store id=%s slug=%s>" % (self.id, self.slug)

    @property
    def id(self) -> str:  # pylint: disable=invalid-name
        """The game's id in its view"""
        return self._game.id

    @property
    def service(self):
        return gtk_safe(self._game.service)

    @property
    def service_media(self):
        return self._service_media

    @property
    def slug(self):
        """Slug identifier"""
        return gtk_safe(self._game.slug)

    @property
    def name(self):
        """Name"""
        return gtk_safe(self._game.name)

    @property
    def sortname(self):
        """Name used for sorting"""
        return gtk_safe(self._game.sortname)

    @property
    def year(self):
        """Year"""
        return str(self._game.year or "")

    @property
    def runner(self):
        """Runner slug"""
        return gtk_safe(self._game.runner) or ""

    @property
    def runner_text(self):
        """Runner name"""
        return gtk_safe(self._game.runner_name)

    @property
    def platform(self):
        """Platform"""
        return gtk_safe(self._game.platform)

    @property
    def installed(self) -> bool:
        """Game is installed"""
        return self._game.installed

    def get_media_paths(self) -> list[MediaPath]:
        """Returns the path to the image file for this item"""
        if self._game.icon:
            return [MediaPath(self._game.icon, self.service_media)]

        possible_paths = self.service_media.get_possible_media_paths(self.slug)
        if any(mp for mp in possible_paths if mp.exists):
            return possible_paths

        service = self._service_obj or LutrisMedia
        services = [(service, lambda: self.slug)]

        game_service_name = self._game.service
        game_service_id = self._game.service_id

        if game_service_name and game_service_id and game_service_name in SERVICES:

            def get_service_slug():
                service_game = ServiceGameCollection.get_game(game_service_name, game_service_id)
                return service_game.get("slug") if service_game else None

            game_service = SERVICES[game_service_name]()
            services.append((game_service, get_service_slug))

        fallback_path = self.service_media.get_fallback_media_path(services)
        return possible_paths + [fallback_path] if fallback_path else possible_paths

    def _get_timestamp_attribute(self, key):
        """Read a timestamp field, discarding and reporting an implausible value. A missing
        value is normal - a game may never have been played or installed - so only a value
        that is present but unusable is worth reporting."""
        value = getattr(self._game, key)
        if not value:
            return None
        timestamp = sanitize_timestamp(value)
        if timestamp is None:
            _report_bad_timestamp(self.name, key, value)
        return timestamp

    @property
    def installed_at(self):
        """Date of install"""
        return self._get_timestamp_attribute("installed_at")

    @property
    def installed_at_text(self):
        """Date of install (textual representation)"""
        return gtk_safe(time.strftime("%X %x", time.localtime(self.installed_at)) if self.installed_at else "")

    @property
    def lastplayed(self):
        """Date of last play"""
        return self._get_timestamp_attribute("lastplayed")

    @property
    def lastplayed_text(self):
        """Date of last play (textual representation)"""
        return gtk_safe(time.strftime("%X %x", time.localtime(self.lastplayed)) if self.lastplayed else "")

    @property
    def playtime(self):
        """Playtime duration in hours"""
        try:
            return float(self._game.playtime or 0)
        except TypeError, ValueError:
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
