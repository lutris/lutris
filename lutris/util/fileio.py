from collections import OrderedDict
from ConfigParser import RawConfigParser


class EvilConfigParser(RawConfigParser):
    """ConfigParser with support for evil INIs using duplicate keys."""
    def write(self, fp):
        for section in self._sections:
            fp.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                if key == "__name__":
                    continue
                if (value is not None) or (self._optcre == self.OPTCRE):
                    # Duplicated keys writing support inside
                    key = "=".join((key,
                                    str(value).replace('\n', '\n%s=' % key)))
                fp.write("%s\n" % (key))
            fp.write("\n")


class MultiOrderedDict(OrderedDict):
    """dict_type to use with an EvilConfigParser instance."""
    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key].extend(value)
        else:
            super(MultiOrderedDict, self).__setitem__(key, value)
