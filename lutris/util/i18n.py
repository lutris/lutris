"""Language and translation utilities"""
import locale
from typing import Optional

from lutris.util.log import logger


def get_user_locale() -> Optional[str]:
    user_locale, _user_encoding = locale.getlocale()
    if not user_locale:
        logger.error("Unable to get locale")
        return None
    return user_locale


def get_lang() -> str:
    """Return the 2 letter language code used by the system"""
    user_locale = get_user_locale()
    if not user_locale:
        return ""
    return user_locale[:2]


# TODO MYPY - return value is quite strange, should be probably Tuple[str, str] but is different
def get_lang_and_country():
    """Return language code and country for the current user"""
    user_locale = get_user_locale()
    if not user_locale:
        return "", ""
    lang_code, country = user_locale.split("-" if "-" in locale else "_")
    return lang_code, country
