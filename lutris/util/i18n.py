"""Language and translation utilities"""

import locale

from lutris.config import LutrisConfig
from lutris.util.log import logger

def get_locale_override():
    """Get a tuple of overridden user locale and encoding values if set"""
    config = LutrisConfig(level="system")
    if config.system_config.get('override_system_locale', False) and config.system_config.get('locale'):
        user_locale, _user_encoding = config.system_config.get('locale').split('.')
        return (user_locale, _user_encoding.replace('utf8', 'UTF8'))
    return (None, None)


def get_user_locale():
    """Get locale for the user, based on optional override, else try system locale"""
    user_locale, _user_encoding = get_locale_override()
    if user_locale:
        return user_locale
    # No valid locale override, try to use system one
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
