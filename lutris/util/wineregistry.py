import os
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
    def __init__(self, reg_filename=None):
        self.arch = None
        self.keys = []
        self.key_map = {}
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
        key_index = 0
        for line in registry_lines:
            # Remove trailing newlines
            line = line.rstrip('\n')
            if line.startswith('#arch'):
                self.arch = line.split('=')[1]
                continue
            if line.startswith('['):
                current_key = WineRegistryKey(line)
                self.keys.append(current_key)
                self.key_map[current_key.name] = key_index
                key_index += 1
                continue
            if current_key:
                if line.startswith('#'):
                    current_key.add_meta(line)
                elif line.startswith('"'):
                    k, v = line.split('=', 1)
                    current_key.set_key(k, v)
                elif line.startswith('@'):
                    k, v = line.split('=', 1)
                    current_key.set_key('default', v)

    def get_key(self, key):
        if key not in self.key_map.keys():
            return
        key_index = self.key_map[key]
        return self.keys[key_index]

    def query(self, keypath, value=None):
        key = self.get_key(keypath)
        if key:
            return key.get_value(value)

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
    def __init__(self, key_def):
        self.raw_name = key_def[:key_def.index(']') + 1]

        # Parse timestamp either as int or float
        self.raw_timestamp = key_def[key_def.index(']') + 1:]
        ts_parts = self.raw_timestamp.strip().split()
        if len(ts_parts) == 1:
            self.timestamp = int(ts_parts[0])
        else:
            self.timestamp = float("{}.{}".format(ts_parts[0], ts_parts[1]))

        self.values = {}
        self.metas = {}
        self.name = self.raw_name.replace('\\\\', '/').strip("[]")

    def set_key(self, name, value):
        self.values[name.strip("\"")] = value.strip()

    def __str__(self):
        return "{0} {1}".format(self.raw_name, self.raw_timestamp)

    def add_meta(self, meta_line):
        if not meta_line.startswith('#'):
            raise ValueError("Key metas should start with '#'")
        meta_line = meta_line[1:]
        key, value = meta_line.split('=')
        self.metas[key] = value

    def get_meta(self, name):
        return self.metas.get(name)

    def get_value(self, name):
        if name not in self.values:
            return
        value = self.values[name]
        if value.startswith("\"") and value.endswith("\""):
            return value[1:-1]
        elif value.startswith('dword:'):
            return int(value[6:], 16)
        else:
            raise ValueError("TODO: finish handling other types")
