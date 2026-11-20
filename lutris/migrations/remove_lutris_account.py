"""This fork doesn't connect to Lutris.net accounts, so forget any that was."""

import os

from lutris import settings
from lutris.util.log import logger

_ACCOUNT_FILES = ("auth-token", "user.json")
_ACCOUNT_SETTINGS = ("library_sync_enabled", "last_library_sync_at", "dismissed_login_notification")


def migrate():
    """Delete the saved Lutris.net token and user details, and the library sync settings"""
    for name in _ACCOUNT_FILES:
        path = os.path.join(settings.CACHE_DIR, name)
        try:
            os.remove(path)
            logger.info("Removed the Lutris.net account file %s", path)
        except FileNotFoundError:
            pass
        except OSError as error:
            logger.warning("Could not remove %s: %s", path, error)

    config = settings.sio.config
    removed = [key for key in _ACCOUNT_SETTINGS if config.has_section("lutris") and config.remove_option("lutris", key)]
    if removed:
        with open(settings.sio.config_file, "w", encoding="utf-8") as config_file:
            config.write(config_file)
