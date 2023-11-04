"""String utilities"""
import math
import re
import shlex
import unicodedata
import uuid
from gettext import gettext as _
from typing import List, Union

from gi.repository import GLib

from lutris.util.log import logger

NO_PLAYTIME = "Never played"


def get_uuid_from_string(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(value)))


def slugify(value) -> str:
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


def add_url_tags(text) -> str:
    """Surround URL with <a> tags."""
    return re.sub(
        r"(http[s]?://("
        r"?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)",
        r'<a href="\1">\1</a>',
        text,
    )


def lookup_string_in_text(string, text):
    """Return full line if string found in the multi-line text."""
    output_lines = text.split("\n")
    for line in output_lines:
        if string in line:
            return line


def parse_version(version):
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
    prefix = version[0:version_match.span()[0]]
    suffix = version[version_match.span()[1]:]
    return [int(p) for p in version_number.split(".")], suffix, prefix


def unpack_dependencies(string: str) -> List[Union[str, tuple]]:
    """Parse a string to allow for complex dependencies
    Works in a similar fashion as Debian dependencies, separate dependencies
    are comma separated and multiple choices for satisfying a dependency are
    separated by pipes.

    Example: quake-steam | quake-gog, some-quake-mod returns:
        [('quake-steam', 'quake-gog'), 'some-quake-mod']
    """

    def _expand_dep(dep) -> Union[str, tuple]:
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


def is_valid_pango_markup(text):
    def destroy_func(_user_data):
        pass  # required by GLib, but we don't need this callback

    if len(text) == 0:
        return True  # Trivial case - empty strings are always valid

    try:
        parser = GLib.MarkupParser()
        context = GLib.MarkupParseContext(parser, GLib.MarkupParseFlags.DEFAULT_FLAGS, None, destroy_func)

        markup = f"<markup>{text}</markup>"
        context.parse(markup, len(markup))
        return True
    except GLib.GError:
        return False


def get_formatted_playtime(playtime) -> str:
    """Return a human readable value of the play time"""
    if not playtime:
        return NO_PLAYTIME

    try:
        playtime = float(playtime)
    except ValueError:
        logger.warning("Invalid playtime value '%s'", playtime)
        return NO_PLAYTIME

    hours = math.floor(playtime)
    if hours == 1:
        hours_text = _("1 hour")
    elif hours > 1:
        hours_text = _("%d hours") % hours
    else:
        hours_text = ""

    minutes = int((playtime - hours) * 60)
    if minutes == 1:
        minutes_text = _("1 minute")
    elif minutes > 1:
        minutes_text = _("%d minutes") % minutes
    else:
        minutes_text = ""

    formatted_time = " ".join([text for text in (hours_text, minutes_text) if text])
    if formatted_time:
        return formatted_time
    if playtime:
        return _("Less than a minute")
    return NO_PLAYTIME


def _split_arguments(args, closing_quot='', quotations=None) -> list:
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


def split_arguments(args) -> list:
    """Wrapper around shlex.split that is more tolerant of errors"""
    if not args:
        # shlex.split seems to hangs when passed the None value
        return []
    return _split_arguments(args)


def human_size(size) -> str:
    """Shows a size in bytes in a more readable way"""
    units = ("bytes", "kB", "MB", "GB", "TB", "PB", "nuh uh", "no way", "BS")
    unit_index = 0
    while size > 1024:
        size = size / 1024
        unit_index += 1
    return "%0.1f %s" % (size, units[unit_index])
