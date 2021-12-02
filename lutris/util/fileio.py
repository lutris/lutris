# Standard Library
import os
import re
from collections import OrderedDict
from configparser import RawConfigParser


def get_unused_directory_path(path):
    """Generates a path to a directory that does not exist, or if it does
    is empty. This is used to make sure multiple installations of the same game
    do not overwrite each other.

    If 'path' is an empty directory or missing entirely, this will return
    'path'. It otherwise appends a number to make it unique."""
    def is_usable_path(path):
        if not os.path.exists(path):
            return True
        return os.path.isdir(path) and not os.listdir(path)

    index = 1
    unused_path = path

    while not is_usable_path(unused_path):
        index += 1  # suffixes start at 2
        unused_path = f"{path}-{index}"

    return unused_path


class EvilConfigParser(RawConfigParser):  # pylint: disable=too-many-ancestors

    """ConfigParser with support for evil INIs using duplicate keys."""

    _SECT_TMPL = r"""
        \[                                 # [
        (?P<header>[^]]+)                  # very permissive!
        \]                                 # ]
        """
    _OPT_TMPL = r"""
        (?P<option>.*?)                    # very permissive!
        \s*(?P<vi>{delim})\s*              # any number of space/tab,
                                           # followed by any of the
                                           # allowed delimiters,
                                           # followed by any space/tab
        (?P<value>.*)$                     # everything up to eol
        """
    _OPT_NV_TMPL = r"""
        (?P<option>.*?)                    # very permissive!
        \s*(?:                             # any number of space/tab,
        (?P<vi>{delim})\s*                 # optionally followed by
                                           # any of the allowed
                                           # delimiters, followed by any
                                           # space/tab
        (?P<value>.*))?$                   # everything up to eol
        """

    # Remove colon from separators since it will mess with some config files
    OPTCRE = re.compile(_OPT_TMPL.format(delim="="), re.VERBOSE)
    OPTCRE_NV = re.compile(_OPT_NV_TMPL.format(delim="="), re.VERBOSE)

    def write(self, fp, space_around_delimiters=True):
        for section in self._sections:
            fp.write("[{}]\n".format(section).encode("utf-8"))
            for (key, value) in list(self._sections[section].items()):
                if key == "__name__":
                    continue
                if (value is not None) or (self._optcre == self.OPTCRE):
                    # Duplicated keys writing support inside
                    key = "=".join((key, str(value).replace("\n", "\n%s=" % key)))
                fp.write("{}\n".format(key).encode("utf-8"))
            fp.write("\n".encode("utf-8"))


class MultiOrderedDict(OrderedDict):

    """dict_type to use with an EvilConfigParser instance."""

    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key].extend(value)
        else:
            super().__setitem__(key, value)
