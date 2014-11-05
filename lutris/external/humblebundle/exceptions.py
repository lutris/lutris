"""
Exception classes for the Humble Bundle API

This module only is guaranteed to only contain exception class definitions
"""

__author__ = "Joel Pedraza"
__copyright__ = "Copyright 2014, Joel Pedraza"
__license__ = "MIT"

__all__ = ['HumbleException', 'HumbleResponseException',
           'HumbleAuthenticationException', 'HumbleCredentialException',
           'HumbleCaptchaException', 'HumbleTwoFactorException',
           'HumbleParseException']

from requests import RequestException


class HumbleException(Exception):
    """
    An unspecified error occurred
    """
    pass


class HumbleResponseException(RequestException, HumbleException):
    """
    A Request completed but the response was somehow invalid or unexpected
    """
    def __init__(self, *args, **kwargs):
        super(HumbleResponseException, self).__init__(*args, **kwargs)


class HumbleAuthenticationException(HumbleResponseException):
    """
    An unspecified authentication failure occurred
    """
    def __init__(self, *args, **kwargs):
        self.captcha_required = kwargs.pop('captcha_required', None)
        self.authy_required = kwargs.pop('authy_required', None)
        super(HumbleAuthenticationException, self).__init__(*args, **kwargs)


class HumbleCredentialException(HumbleAuthenticationException):
    """
    Username and password don't match
    """
    pass


class HumbleCaptchaException(HumbleAuthenticationException):
    """
    The CAPTCHA response was invalid
    """
    pass


class HumbleTwoFactorException(HumbleAuthenticationException):
    """
    The one time password was invalid
    """
    pass


class HumbleParseException(HumbleResponseException):
    """
    An error occurred while parsing
    """
    pass
