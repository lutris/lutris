"""Exception handling module"""
# Standard Library
from functools import wraps
from gettext import gettext as _


class LutrisError(Exception):

    """Base exception for Lutris related errors"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class GameConfigError(LutrisError):

    """Throw this error when the game configuration prevents the game from
    running properly.
    """


class UnavailableLibraries(RuntimeError):

    def __init__(self, libraries, arch=None):
        message = _(
            "The following {arch} libraries are required but are not installed on your system:\n{libs}"
        ).format(
            arch=arch if arch else "",
            libs=", ".join(libraries)
        )
        super().__init__(message)
        self.libraries = libraries


class AuthenticationError(Exception):
    """Raised when authentication to a service fails"""


class UnavailableGame(Exception):
    """Raised when a game is available from a service"""


class MultipleInstallerError(BaseException):

    """Current implementation doesn't know how to deal with multiple installers
    Raise this if a game returns more than 1 installer."""


def watch_lutris_errors(function):
    """Decorator used to catch LutrisError exceptions and send events"""

    @wraps(function)
    def wrapper(*args, **kwargs):
        """Catch all LutrisError exceptions and emit an event."""
        try:
            return function(*args, **kwargs)
        except LutrisError as ex:
            game = args[0]
            game.emit("game-error", ex.message)

    return wrapper
