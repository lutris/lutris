import os

TYPES = {
    'str': 'REG_SZ',
    'str(2)': 'REG_EXPAND_SZ',
    'dword': 'REG_DWORD',
    'hex': 'REG_BINARY',
}


class WineRegistry(object):
    def __init__(self, reg_filename=None):
        self.arch = None
        self.keys = {}
        self.key_order = []
        self.prefix_path = None
        if reg_filename:
            self.parse_reg_file(reg_filename)

    def parse_reg_file(self, reg_filename):
        with open(reg_filename, 'r') as reg_file:
            registry_content = reg_file.readlines()
        self.prefix_path = os.path.dirname(os.path.abspath(reg_filename))
        current_key = None
        for line in registry_content:
            if line.startswith('#arch'):
                self.arch = line.split('=')[1]
                continue
            if line.startswith('['):
                key, timestamp = line.strip().rsplit(' ', 1)
                current_key = WineRegistryKey(key)
                current_key.timestamp = timestamp
                self.keys[current_key.name] = current_key
                self.key_order.append(current_key.name)
                continue
            if current_key:
                if line.startswith('"'):
                    k, v = line.split('=', 1)
                    current_key.set_key(k, v)
                elif line.startswith('@'):
                    k, v = line.split('=', 1)
                    current_key.set_key('default', v)

    def query(self, keypath, value=None):
        if keypath not in self.keys:
            return
        key = self.keys[keypath]
        return key.get_value(value)

    def get_unix_path(self, windows_path):
        windows_path = windows_path.replace('\\\\', '/')
        if not self.prefix_path:
            return
        old_cwd = os.getcwd()
        drives_path = os.path.join(self.prefix_path, "dosdevices")
        os.chdir(drives_path)
        if not os.path.exists(drives_path):
            return
        letter, relpath = windows_path.split(':', 1)
        relpath = relpath.strip('/')
        drive_link = os.path.join(drives_path, letter.lower() + ":")
        drive_path = os.path.abspath(os.readlink(drive_link))
        os.chdir(old_cwd)
        return os.path.join(drive_path, relpath)


class WineRegistryKey(object):
    def __init__(self, key):
        self.timestamp = None
        self.values = {}
        self.name = key.replace('\\\\', '/').strip("[]")

    def set_key(self, name, value):
        self.values[name.strip("\"")] = value.strip()

    def __str__(self):
        return "[{0}] {1}".format(self.winname, self.timestamp)

    @property
    def winname(self):
        return self.name.replace('/', '\\\\')

    def show_key(self, name):
        return "\"{0}\"={1}".format(name, self.values[name])

    def get_value(self, name):
        if name not in self.values:
            return
        value = self.values[name]
        if value.startswith("\"") and value.endswith("\""):
            return value[1:-1]
        else:
            raise ValueError("TODO: finish handling other types")

if __name__ == "__main__":
    registry = WineRegistry(os.path.expanduser("~/.wine/user.reg"))
    for keyname in registry.keys:
        key = registry.keys[keyname]
        print key
        for name in key.values:
            print key.show_key(name)
        print

    steam_key = "Software/Valve/Steam"
    print "Querying registry for {}".format(steam_key)
    q = registry.query(steam_key, "SteamExe")
    print q
