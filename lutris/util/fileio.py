# Standard Library
import re
from collections import OrderedDict
from configparser import RawConfigParser


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
            super(MultiOrderedDict, self).__setitem__(key, value)
