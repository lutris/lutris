import unicodedata
import re


def slugify(value):
    """Remove special characters from a string and slugify it.

    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = value.decode('utf-8')
    value = str(re.sub('[^\w\s-]', '', value)).strip().lower()
    return re.sub('[-\s]+', '-', value)


def add_url_tags(text):
    """Surround URL with <a> tags."""
    return re.sub(
        r'(http[s]?://('
        r'?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)',
        r'<a href="\1">\1</a>',
        text
    )


def lookup_string_in_text(string, text):
    """Return full line if string found in the multi-line text."""
    output_lines = text.split('\n')
    for line in output_lines:
        if string in line:
            return line


def version_sort(versions, reverse=False):
    def version_key(version):
        version_match = re.search(r'(\d[\d\.]+\d)', version)
        if not version_match:
            return
        version_number = version_match.groups()[0]
        prefix = version[0:version_match.span()[0]]
        suffix = version[version_match.span()[1]:]
        version = [int(p) for p in version_number.split('.')]
        version = version + [0] * (10 - len(version))
        version.append(prefix)
        version.append(suffix)
        return version
    return sorted(versions, key=version_key, reverse=reverse)
