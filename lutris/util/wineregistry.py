import os
from collections import OrderedDict
from datetime import datetime

TYPES = {
    'str': 'REG_SZ',
    'str(2)': 'REG_EXPAND_SZ',
    'dword': 'REG_DWORD',
    'hex': 'REG_BINARY',
}


class WindowsFileTime:
    """Utility class to deal with Windows FILETIME structures.

    See: https://msdn.microsoft.com/en-us/library/ms724284(v=vs.85).aspx
    """
    ticks_per_seconds = 10000000  # 1 tick every 100 nanoseconds
    epoch_delta = 11644473600  # 3600 * 24 * ((1970 - 1601) * 365 + 89)

    def __init__(self, timestamp=None):
        self.timestamp = timestamp

    def __repr__(self):
        return "<{}>: {}".format(self.__class__.__name__, self.timestamp)

    @classmethod
    def from_hex(cls, hexvalue):
        timestamp = int(hexvalue, 16)
        return WindowsFileTime(timestamp)

    def to_hex(self):
        return '{:x}'.format(self.timestamp)

    @classmethod
    def from_unix_timestamp(cls, timestamp):
        timestamp = timestamp + cls.epoch_delta
        timestamp = int(timestamp * cls.ticks_per_seconds)
        return WindowsFileTime(timestamp)

    def to_unix_timestamp(self):
        if not self.timestamp:
            raise ValueError("No timestamp set")
        unix_ts = self.timestamp / self.ticks_per_seconds
        unix_ts = unix_ts - self.epoch_delta
        return unix_ts

    def to_date_time(self):
        return datetime.fromtimestamp(self.to_unix_timestamp())


class WineRegistry(object):
    version_header = "WINE REGISTRY Version "
    relative_to_header = ";; All keys relative to "

    def __init__(self, reg_filename=None):
        self.arch = 'win32'
        self.version = 2
        self.relative_to = "\\\\User\\\\S-1-5-21-0-0-0-1000"
        self.keys = OrderedDict()
        if reg_filename:
            self.prefix_path = os.path.dirname(reg_filename)
            self.parse_reg_file(reg_filename)

    def get_raw_registry(self, reg_filename):
        """Return an array of the unprocessed contents of a registry file"""
        with open(reg_filename, 'r') as reg_file:
            registry_content = reg_file.readlines()
        return registry_content

    def parse_reg_file(self, reg_filename):
        registry_lines = self.get_raw_registry(reg_filename)
        current_key = None
        for line in registry_lines:
            line = line.rstrip('\n')  # Remove trailing newlines

            if line.startswith(self.version_header):
                self.version = int(line[len(self.version_header):])
                continue

            if line.startswith(self.relative_to_header):
                self.relative_to = line[len(self.relative_to_header):]
                continue

            if line.startswith('#arch'):
                self.arch = line.split('=')[1]
                continue

            if line.startswith('['):
                current_key = WineRegistryKey(key_def=line)
                self.keys[current_key.name] = current_key
                continue

            if current_key:
                current_key.parse(line)

    def render(self):
        content = ""
        content += "{}{}\n".format(self.version_header, self.version)
        content += "{}{}\n\n".format(self.relative_to_header, self.relative_to)
        content += "#arch={}\n".format(self.arch)
        for key in self.keys:
            content += "\n"
            content += self.keys[key].render()
        return content

    def query(self, keypath, value=None):
        key = self.keys.get(keypath)
        if key:
            return key.get_subkey(value)

    def get_unix_path(self, windows_path):
        windows_path = windows_path.replace('\\\\', '/')
        if not self.prefix_path:
            return
        drives_path = os.path.join(self.prefix_path, "dosdevices")
        if not os.path.exists(drives_path):
            return
        letter, relpath = windows_path.split(':', 1)
        relpath = relpath.strip('/')
        drive_link = os.path.join(drives_path, letter.lower() + ":")
        drive_path = os.readlink(drive_link)
        if not os.path.isabs(drive_path):
            drive_path = os.path.join(drives_path, drive_path)
        return os.path.join(drive_path, relpath)


class WineRegistryKey(object):
    def __init__(self, key_def=None):
        self.raw_name = key_def[:key_def.index(']') + 1]

        # Parse timestamp either as int or float
        self.raw_timestamp = key_def[key_def.index(']') + 1:]
        ts_parts = self.raw_timestamp.strip().split()
        if len(ts_parts) == 1:
            self.timestamp = int(ts_parts[0])
        else:
            self.timestamp = float("{}.{}".format(ts_parts[0], ts_parts[1]))

        self.subkeys = OrderedDict()
        self.metas = OrderedDict()
        self.name = self.raw_name.replace('\\\\', '/').strip("[]")

    def __str__(self):
        return "{0} {1}".format(self.raw_name, self.raw_timestamp)

    def parse(self, line):
        if line.startswith('#'):
            self.add_meta(line)
        elif line.startswith('"'):
            key, value = line.split('=', 1)
            self.set_subkey(key, value)
        elif line.startswith('@'):
            k, v = line.split('=', 1)
            self.set_subkey('default', v)

    def render(self):
        """Return the content of the key in the wine .reg format"""
        content = self.raw_name + self.raw_timestamp + "\n"
        for key, value in self.metas.items():
            if value is None:
                content += "#{}".format(key)
            else:
                content += "#{}={}\n".format(key, value)
        for key, value in self.subkeys.items():
            if key == 'default':
                key = '@'
            else:
                key = "\"{}\"".format(key)
            content += "{}={}\n".format(key, value)
        return content

    def render_value(self, value):
        if isinstance(value, int):
            return "dword:{:08x}".format(value)
        elif isinstance(value, str):
            print(value)
            return "\"{}\"\n".format(value)

    def add_meta(self, meta_line):
        if not meta_line.startswith('#'):
            raise ValueError("Key metas should start with '#'")
        meta_line = meta_line[1:]
        parts = meta_line.split('=')
        if len(parts) == 2:
            key = parts[0]
            value = parts[1]
        elif len(parts) == 1:
            key = parts[0]
            value = None
        else:
            raise ValueError("Invalid meta line '{}'".format(meta_line))
        self.metas[key] = value

    def get_meta(self, name):
        return self.metas.get(name)

    def set_subkey(self, name, value):
        self.subkeys[name.strip("\"")] = value.strip()

    def get_subkey(self, name):
        if name not in self.subkeys:
            return
        value = self.subkeys[name]
        if value.startswith("\"") and value.endswith("\""):
            return value[1:-1]
        elif value.startswith('dword:'):
            return int(value[6:], 16)
        else:
            raise ValueError("TODO: finish handling other types")
