"""Language and translation utilities"""
import locale


def get_lang():
    """Return the 2 letter language code used by the system"""
    user_locale, _user_encoding = locale.getlocale()
    return user_locale[:2]


def get_lang_and_country():
    """Return language code and country for the current user"""
    user_locale, _user_encoding = locale.getlocale()
    lang_code, country = user_locale.split('-' if '-' in locale else '_')
    return lang_code, country
