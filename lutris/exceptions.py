"""Exception handling module"""
from functools import wraps
from gettext import gettext as _

from lutris.util.log import logger


class LutrisError(Exception):

    """Base exception for Lutris related errors"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class GameConfigError(LutrisError):

    """Throw this error when the game configuration prevents the game from
    running properly.
    """


class UnavailableLibrariesError(RuntimeError):

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


class UnavailableGameError(Exception):
    """Raised when a game is unavailable from a service"""


class UnavailableRunnerError(Exception):
    """Raised when a runner is not installed or not installed fully."""


def watch_errors(error_result=None, handler_object=None):
    """Decorator used to catch exceptions for GUI signal handlers. This
    catches any exception from the decorated function and calls
    on_watch_errors(error) on the first argument, which we presume to be self.
    and then the method will return 'error_result'"""
    captured_handler_object = handler_object

    def inner_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            myself = captured_handler_object or args[0]
            try:
                return function(*args, **kwargs)
            except Exception as ex:
                logger.exception(str(ex), exc_info=ex)
                myself.on_watched_error(ex)
                return error_result
        return wrapper
    return inner_decorator


def watch_game_errors(game_stop_result, game=None):
    """Decorator used to catch exceptions and send events instead of propagating them normally.
    If 'game_stop_result' is not None, and the decorated function returns that, this will
    send game-stop and make the game stopped as well. This simplifies handling cancellation.
    Also, if an error occurs and is emitted, the function returns this value, so callers
    can tell that the function failed.

    If you do not provide a game object directly, it is assumed to be in the first argument to
    the decorated method (which is 'self', typically).
    """
    captured_game = game

    def inner_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            """Catch all exceptions and emit an event."""
            game = captured_game if captured_game else args[0]

            try:
                result = function(*args, **kwargs)
                if game_stop_result is not None and result == game_stop_result and game.state != game.STATE_STOPPED:
                    game.state = game.STATE_STOPPED
                    game.emit("game-stop")
                return result
            except Exception as ex:
                logger.exception("%s has encountered an error: %s", game, ex, exc_info=ex)
                if game.state != game.STATE_STOPPED:
                    game.state = game.STATE_STOPPED
                    game.emit("game-stop")
                game.signal_error(ex)
                return game_stop_result

        return wrapper
    return inner_decorator
