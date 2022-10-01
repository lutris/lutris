"""Exception handling module"""
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


class UnavailableRunnerError(Exception):
    """Raised when a runner is not installed or not installed fully."""


def watch_errors(function):
    """Decorator used to catch exceptions for GUI signal handlers. This
    catches any exception from the decorated function and calls
    on_watch_errors(error) on the first argument, which we presume to be self."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        myself = args[0]
        try:
            return function(*args, **kwargs)
        except Exception as ex:
            return myself.on_watched_error(ex)
    return wrapper


def watch_game_errors(game_stop_result):
    """Decorator used to catch exceptions and send events instead of propagating them normally.
    If 'game_stop_result' is not None, and the decorated function returns that, this will
    send game-stop and make the game stopped as well. This simplifies handling cancellation.
    Also, if an error occurs and is emitted, the function returns this value, so callers
    can tell that the function failed.
    """

    def inner_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            """Catch all exceptions and emit an event."""
            game = args[0]
            try:
                result = function(*args, **kwargs)
                if game_stop_result is not None and result == game_stop_result and game.state != game.STATE_STOPPED:
                    game.state = game.STATE_STOPPED
                    game.emit("game-stop")
                return result
            except Exception as ex:
                if game.state != game.STATE_STOPPED:
                    game.state = game.STATE_STOPPED
                    game.emit("game-stop")
                game.emit("game-error", ex)
                return game_stop_result

        return wrapper
    return inner_decorator
