"""Language and translation utilities"""

import locale

from lutris.config import LutrisConfig
from lutris.util.log import logger


def get_user_locale():
    """Get locale for the user, based on global options, else try system locale"""
    config = LutrisConfig(level="system")
    if config.system_config.get("locale"):
        try:
            user_locale, _user_encoding = config.system_config["locale"].split(".")
            return user_locale
        except ValueError:  # If '.' is not found
            return config.system_config["locale"]

    user_locale, _user_encoding = locale.getlocale()
    if not user_locale:
        logger.error("Unable to get locale")
        return
    return user_locale


def get_lang():
    """Return the 2 letter language code used by the system"""
    user_locale = get_user_locale()
    if not user_locale:
        return ""
    return user_locale[:2]


def get_lang_and_country():
    """Return language code and country for the current user"""
    user_locale = get_user_locale()
    if not user_locale:
        return "", ""
    lang_code, country = user_locale.split("-" if "-" in locale else "_")
    return lang_code, country
