import unicodedata
import re


def slugify(value):
    """Remove special characters from a string and slugify it.

    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii',
                                                                 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)


def add_url_tags(text):
    """ Surrounds URL with <a> tags """
    return re.sub(
        r'(http[s]?://('
        r'?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)',
        r'<a href="\1">\1</a>',
        text
    )
