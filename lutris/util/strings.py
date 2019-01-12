import unicodedata
import re
import math


def slugify(value):
    """Remove special characters from a string and slugify it.

    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = str(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore")
    value = value.decode("utf-8")
    value = str(re.sub(r"[^\w\s-]", "", value)).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def add_url_tags(text):
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
    return [int(p) for p in version_number.split(".")], prefix, suffix


def version_sort(versions, reverse=False):
    def version_key(version):
        version_list, prefix, suffix = parse_version(version)
        # Normalize the length of sub-versions
        sort_key = version_list + [0] * (10 - len(version_list))
        sort_key.append(prefix)
        sort_key.append(suffix)
        return sort_key

    return sorted(versions, key=version_key, reverse=reverse)


def unpack_dependencies(string):
    """Parse a string to allow for complex dependencies
    Works in a similar fashion as Debian dependencies, separate dependencies
    are comma separated and multiple choices for satisfying a dependency are
    separated by pipes.

    Example: quake-steam | quake-gog, some-quake-mod returns:
        [('quake-steam', 'quake-gog'), 'some-quake-mod']
    """
    if not string:
        return []
    dependencies = [dep.strip() for dep in string.split(",") if dep.strip()]
    for index, dependency in enumerate(dependencies):
        if "|" in dependency:
            dependencies[index] = tuple(
                [option.strip() for option in dependency.split("|") if option.strip()]
            )
    return [dependency for dependency in dependencies if dependency]


def gtk_safe(string):
    """Return a string ready to used in Gtk widgets"""
    if not string:
        string = ""
    return string.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_gtk_label(string):
    """Used to escape some characters for display in Gtk labels"""
    return re.sub("&(?!amp;)", "&amp;", string)


def get_formatted_playtime(playtime):
    """Return a human readable value of the play time"""
    if not playtime:
        return "No play time recorded"

    try:
        playtime = float(playtime)
    except TypeError:
        return "Invalid playtime %s" % playtime
    hours = math.floor(playtime)

    if hours:
        hours_text = "%d hour%s" % (hours, "s" if hours > 1 else "")
    else:
        hours_text = ""

    minutes = int((playtime - hours) * 60)
    if minutes:
        minutes_text = "%d minute%s" % (minutes, "s" if minutes > 1 else "")
    else:
        minutes_text = ""

    return " and ".join([text for text in (hours_text, minutes_text) if text]) or "0 minute"
