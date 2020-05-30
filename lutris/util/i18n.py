"""Language and translation utilities"""
# Standard Library
import locale


def get_lang():
    """Return the 2 letter language code used by the system"""
    user_locale, _user_encoding = locale.getlocale()
    return user_locale[:2]
