"""String utilities"""

import math
import re
import shlex
import time
import unicodedata
import uuid
from dataclasses import dataclass
from gettext import gettext as _
from typing import List, Optional, Tuple, Union

from gi.repository import GLib  # type: ignore

from lutris.util.log import logger

NO_PLAYTIME = _("Never played")


def get_uuid_from_string(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(value)))


def slugify(value: str) -> str:
    """Remove special characters from a string and slugify it.

    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    _value = str(value)
    # This differs from the Lutris website implementation which uses the Django
    # version of `slugify` and uses the "NFKD" normalization method instead of
    # "NFD". This creates some inconsistencies in titles containing a trademark
    # symbols or some other special characters. The website version of slugify
    # will likely get updated to use the same normalization method.
    _value = unicodedata.normalize("NFD", _value).encode("ascii", "ignore")
    _value = _value.decode("utf-8")
    _value = str(re.sub(r"[^\w\s-]", "", _value)).strip().lower()
    slug = re.sub(r"[-\s]+", "-", _value)
    if not slug:
        # The slug is empty, likely because the string contains only non-latin
        # characters
        slug = get_uuid_from_string(value)
    return slug


def strip_accents(value: str) -> str:
    """Returns a string that is 'value', but with combining characters removed.

    This normalizes the text to form KD, which also removes any compatibility characters,
    so things like ellipsis are expanded to '...'.

    This also strips leading a trailing whitespace, and normalizes all remaining whitespace
    to single spaces.

    This does allow non-ASCII characters (like Greek or Cyrillic), and does not interfere with
    casing.

    We use this for a more forgiving search.
    """
    if value:
        decomposed = unicodedata.normalize("NFKD", value)
        result = ""
        prev_whitespace = False
        for ch in reversed(decomposed.strip()):
            combining = unicodedata.combining(ch)
            if not combining:
                whitespace = ch.isspace()
                if whitespace:
                    if not prev_whitespace:
                        result += " "
                else:
                    result += ch
                prev_whitespace = whitespace
        return result[::-1]  # We built the text backwards, so we must reverse it
    return value


def get_natural_sort_key(value: str, number_width: int = 16) -> str:
    """Returns a string with the numerical parts (runs of digits)
    0-padded out to 'number_width' digits."""

    def pad_numbers(text):
        return text.zfill(number_width) if text.isdigit() else text.casefold()

    runs = [pad_numbers(c) for c in re.split("([0-9]+)", value)]
    return "".join(runs)


def lookup_strings_in_text(string: str, text: str) -> List[str]:
    """Return each full line where a string was found in the multi-line text."""
    input_lines = text.split("\n")
    return [line for line in input_lines if string in line]


def parse_version(version: str) -> Tuple[List[int], str, str]:
    """Parse a version string

    Return a 3 element tuple containing:
     - The version number as a list of integers
     - The prefix (whatever characters before the version number)
     - The suffix (whatever comes after)

     Example::
        >>> parse_version("3.6-staging")
        ([3, 6], '', '-staging')

    Returns:
        tuple: (version number as list, prefix, suffix)
    """
    version_match = re.search(r"(\d[\d\.]+\d)", version)
    if not version_match:
        return [], "", ""
    version_number = version_match.groups()[0]
    prefix = version[0 : version_match.span()[0]]
    suffix = version[version_match.span()[1] :]
    return [int(p) for p in version_number.split(".")], suffix, prefix


def unpack_dependencies(string: str) -> List[Union[str, tuple]]:
    """Parse a string to allow for complex dependencies
    Works in a similar fashion as Debian dependencies, separate dependencies
    are comma separated and multiple choices for satisfying a dependency are
    separated by pipes.

    Example: quake-steam | quake-gog, some-quake-mod returns:
        [('quake-steam', 'quake-gog'), 'some-quake-mod']
    """

    def _expand_dep(dep: str) -> Union[str, tuple]:
        if "|" in dep:
            return tuple(option.strip() for option in dep.split("|") if option.strip())
        return dep.strip()

    if not string:
        return []
    return [dep for dep in [_expand_dep(dep) for dep in string.split(",")] if dep]


def gtk_safe(text: str) -> str:
    """Return a string ready to used in Gtk widgets, with anything that could
    be Pango markup escaped."""
    if not text:
        return ""

    return GLib.markup_escape_text(str(text))


def gtk_safe_urls(text: str) -> str:
    """Escapes the text as with gtk_safe, but detects URLs and converts them to
    anchor tags as well."""
    if not text:
        return ""

    parts = re.split(r"(http[s]?://(" r"?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)", text)

    for index, part in enumerate(parts):
        if len(part) > 0:
            part = gtk_safe(part)
            if index % 2 != 0:  # every odd numbered part is the group in the regular expression
                part = f'<a href="{part}">{part}</a>'
            parts[index] = part

    return "".join(parts)


def is_valid_pango_markup(text: str) -> bool:
    def destroy_func(_user_data):
        pass  # required by GLib, but we don't need this callback

    if len(text) == 0:
        return True  # Trivial case - empty strings are always valid

    try:
        parser = GLib.MarkupParser()
        # DEFAULT_FLAGS == 0, but was not defined before GLib 2.74 so
        # we'll just hard-code the value.
        parser_flags: GLib.MarkupParseFlags = 0  # type: ignore
        context = GLib.MarkupParseContext.new(
            parser=parser, flags=parser_flags, user_data=None, user_data_dnotify=destroy_func
        )

        markup = f"<markup>{text}</markup>"
        context.parse(markup, len(markup))
        return True
    except GLib.GError:  # type: ignore
        return False


def get_formatted_playtime(playtime: float) -> str:
    """Return a human-readable value of the play time"""
    if not playtime:
        return NO_PLAYTIME

    try:
        playtime = float(playtime)
    except ValueError:
        logger.warning("Invalid playtime value '%s'", playtime)
        return NO_PLAYTIME

    hours = math.floor(playtime)
    minutes = int(round((playtime - hours) * 60, 0))

    # If we're close enough to the next hour, we might wind up
    # with "x hours 60 minutes" and that looks dumb.
    if minutes >= 60:
        minutes -= 60
        hours += 1

    hours_unit = _("hour") if hours == 1 else _("hours")
    hours_text = f"{hours} {hours_unit}" if hours > 0 else ""
    minutes_unit = _("minute") if minutes == 1 else _("minutes")
    minutes_text = f"{minutes} {minutes_unit}" if minutes > 0 else ""

    formatted_time = " ".join([text for text in (hours_text, minutes_text) if text])
    if formatted_time:
        return formatted_time
    if playtime:
        return _("Less than a minute")
    return NO_PLAYTIME


def parse_playtime(text: str) -> float:
    """Parses a textual playtime into hours"""
    playtime = parse_playtime_parts(text)
    return playtime.get_total_hours()


@dataclass
class PlaytimeParts:
    years: float = 0.0
    months: float = 0.0
    weeks: float = 0.0
    days: float = 0.0
    hours: float = 0.0
    minutes: float = 0.0

    def is_empty(self) -> bool:
        return not (self.years or self.months or self.weeks or self.days or self.hours or self.minutes)

    def get_total_hours(self) -> float:
        return (
            self.hours
            + self.minutes / 60
            + self.days * 24
            + self.weeks * 24 * 7
            + self.months * 24 * 30
            + self.years * 24 * 365
        )

    def matches(self, hours: float) -> bool:
        total_hours = self.get_total_hours()
        if self.minutes != 0.0:
            return math.isclose(total_hours * 60, round(hours * 60, 0))
        if self.hours != 0.0:
            return math.isclose(total_hours, round(hours, 0))
        if self.days != 0.0:
            return math.isclose(total_hours / 24, round(hours / 24, 0))
        if self.weeks != 0.0:
            hours_per_week = 24 * 7
            return math.isclose(total_hours / hours_per_week, round(hours / hours_per_week, 0))
        if self.months != 0.0:
            hours_per_month = 24 * 30
            return math.isclose(total_hours / hours_per_month, round(hours / hours_per_month, 0))
        if self.years != 0.0:
            hours_per_year = 24 * 365
            return math.isclose(total_hours / hours_per_year, round(hours / hours_per_year, 0))

        # if 0 overall, treat as 0 minutes
        return math.isclose(total_hours * 60, round(hours * 60, 0))

    def add_part(self, num: float, unit: str) -> bool:
        # This function works out how many hours are meant by some
        # number of some unit.
        hour_units = ["h", "hr", "hours", "hour", _("hour"), _("hours")]
        minute_units = ["m", "min", "minute", "minutes", _("minute"), _("minutes")]
        day_units = ["d", _("day"), _("days")]
        week_units = ["wk", _("week"), _("weeks")]
        month_units = ["mo", _("month"), _("months")]
        year_units = ["yr", _("year"), _("years")]
        if unit in hour_units:
            self.hours += num
        elif unit in minute_units:
            self.minutes += num
        elif unit in day_units:
            self.days += num
        elif unit in week_units:
            self.weeks += num
        elif unit in month_units:
            self.months += num
        elif unit in year_units:
            self.years += num
        else:
            return False

        return True


def parse_playtime_parts(text: str) -> PlaytimeParts:
    text = text.strip().casefold()

    playtime = PlaytimeParts()

    if _("Less than a minute").casefold() == text:
        return playtime

    if NO_PLAYTIME.casefold() == text:
        return playtime

    error_message = _("'%s' is not a valid playtime.") % text

    # Handle a single number - assumed to be a count of hours
    try:
        playtime.hours = float(text)
        return playtime
    except ValueError:
        pass

    # Handle the easy case of "6:23".
    parts = text.split(":")
    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
        try:
            playtime.hours = int(parts[0])
            playtime.minutes = int(parts[1])
            return playtime
        except ValueError as ex:
            raise ValueError(error_message) from ex

    # Handle the fancy format made of number unit pairts, like
    # "1 hour 23 minutes" or "2h57m"; we split this up into digit
    # and non-digit parts.
    parts = [p.strip() for p in re.split("([0-9.,]+)", text) if p and not p.isspace()]
    parts_iter = iter(parts)

    try:
        while True:
            num_text = next(parts_iter)
            try:
                num = float(num_text)
            except ValueError as ex:
                raise ValueError(error_message) from ex

            try:
                unit = next(parts_iter)
            except StopIteration as ex:
                if not playtime.is_empty():
                    unit = "minutes"
                else:
                    raise ValueError(error_message) from ex

            if not playtime.add_part(num, unit):
                raise ValueError(error_message)
    except StopIteration:
        pass

    return playtime


def _split_arguments(args: str, closing_quot: str = "", quotations: Optional[List[str]] = None) -> List[str]:
    if quotations is None:
        quotations = ["'", '"']
    try:
        return shlex.split(args + closing_quot)
    except ValueError as ex:
        message = ex.args[0]
        if message == "No closing quotation" and quotations:
            return _split_arguments(args, quotations[0], quotations[1:])
        logger.error(message)
        return []


def split_arguments(args: str) -> List[str]:
    """Wrapper around shlex.split that is more tolerant of errors"""
    if not args:
        # shlex.split seems to hangs when passed the None value
        return []
    return _split_arguments(args)


def human_size(size: float) -> str:
    """Shows a size in bytes in a more readable way"""
    units = ("bytes", "kB", "MB", "GB", "TB", "PB", "nuh uh", "no way", "BS")
    unit_index = 0
    while size > 1024:
        size = size / 1024
        unit_index += 1
    return "%0.1f %s" % (size, units[unit_index])


def time_ago(timestamp: float) -> str:
    time_delta = time.time() - timestamp

    original_time_delta = time_delta
    if time_delta < 0:
        return _("in the future")
    if time_delta < 5:
        return _("just now")
    parts = []
    day_in_seconds = 3600 * 24
    hour_in_seconds = 3600
    days = 0
    hours = 0
    if time_delta >= 2 * day_in_seconds:
        days = int(time_delta // day_in_seconds)
        time_delta = time_delta - days * day_in_seconds
        parts.append(_("%d days") % days)
    if time_delta > 2 * hour_in_seconds:
        hours = int(time_delta // hour_in_seconds)
        time_delta = time_delta - hours * hour_in_seconds
        parts.append(_("%d hours") % hours)
    if not days and hours < 5 and time_delta > 60:
        minutes = int(time_delta // 60)
        time_delta = time_delta - minutes * 60
        if minutes != 1:
            parts.append(_("%d minutes") % minutes)
        else:
            parts.append(_("1 minute"))
    if original_time_delta < 90:
        seconds = int(time_delta)
        if seconds != 1:
            parts.append(_("%d seconds") % seconds)
        else:
            parts.append(_("1 second"))

    parts.append(_("ago"))
    return " ".join(parts)
