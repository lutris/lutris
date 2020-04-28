"""Manipulate MAME ini files"""
from lutris.util.system import path_exists


class MameIni:
    """Looks like an ini file and yet it is not one!"""
    def __init__(self, ini_path):
        if not path_exists(ini_path):
            raise OSError("File %s does not exist" % ini_path)
        self.ini_path = ini_path
        self.lines = []
        self.config = {}

    def parse(self, line):
        """Store configuration value from a line"""
        line = line.strip()
        if not line or line.startswith("#"):
            return None, None
        key, *_value = line.split(maxsplit=1)
        if _value:
            return key, _value[0]
        return key, None

    def read(self):
        """Reads the content of the ini file"""
        with open(self.ini_path, "r") as ini_file:
            for line in ini_file.readlines():
                self.lines.append(line)
                print(line)
                config_key, config_value = self.parse(line)
                if config_key:
                    self.config[config_key] = config_value

    def write(self):
        """Writes the file to disk"""
        with open(self.ini_path, "w") as ini_file:
            for line in self.lines:
                config_key, _value = self.parse(line)
                if config_key and self.config[config_key]:
                    ini_file.write("%-26s%s\n" % (config_key, self.config[config_key]))
                elif config_key:
                    ini_file.write("%s\n" % config_key)
                else:
                    ini_file.write(line)
