"""Exception handling module"""
from functools import wraps


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
    def __init__(self, libraries):
        message = (
            "Some required libraries are not installed on your system, install them "
            "with your package manager and restart Lutris. Libraries: %s"
        ) % ", ".join(libraries)
        super().__init__(message)
        self.libraries = libraries


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
