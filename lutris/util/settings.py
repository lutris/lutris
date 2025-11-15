import configparser
import os

from lutris.gui.widgets import NotificationSource
from lutris.util.log import logger


class SettingsIO:
    """ConfigParser abstraction."""

    def __init__(self, config_file):
        self.config_file = config_file
        self.config = configparser.ConfigParser()

        # A notification that fires on each settings change
        self.SETTINGS_CHANGED = NotificationSource()  # called with (setting-key, new-value, section)

        if os.path.exists(self.config_file):
            try:
                self.config.read([self.config_file])
            except configparser.ParsingError as ex:
                logger.error("Failed to readconfig file %s: %s", self.config_file, ex)
            except UnicodeDecodeError as ex:
                logger.error("Some invalid characters are preventing the setting file from loading properly: %s", ex)

    def read_setting(self, key, default="", section="lutris"):
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

    def read_bool_setting(self, key: str, default: bool = False, section="lutris") -> bool:
        text = self.read_setting(key, "", section=section).casefold()
        if text == "true":
            return True
        if text == "false":
            return False

        return default

    def write_setting(self, key, value, section="lutris"):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

        with open(self.config_file, "w", encoding="utf-8") as config_file:
            self.config.write(config_file)

        self.SETTINGS_CHANGED.fire(key, value, section)
