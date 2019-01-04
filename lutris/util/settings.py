import os
import configparser


class SettingsIO:
    """ConfigParser abstraction."""

    def __init__(self, config_file):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            self.config.read([self.config_file])

    def read_setting(self, key, section="lutris", default=None):
        """Read a setting from the config file

        Params:
            key (str): Setting key
            section (str): Optional section, default to 'lutris'
            default (str): Default value to return if setting not present
        """
        try:
            return self.config.get(section, key)
        except (configparser.NoOptionError, configparser.NoSectionError):
            return default

    def write_setting(self, key, value, section="lutris"):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

        with open(self.config_file, "w") as config_file:
            self.config.write(config_file)
