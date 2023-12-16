"""Exception handling module"""
from functools import wraps
from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk

from lutris.gui.dialogs import ErrorDialog
from lutris.util.log import logger


class LutrisError(Exception):
    """Base exception for Lutris related errors"""

    def __init__(self, message, *args, **kwarg):
        super().__init__(message, *args, **kwarg)
        self.message = message


class MisconfigurationError(LutrisError):
    """Raised for incorrect configuration or installation, like incorrect
    or missing settings, missing components, that sort of thing. This has subclasses
    that are less vague."""


class GameConfigError(MisconfigurationError):
    """Throw this error when the game configuration prevents the game from
    running properly."""


class AuthenticationError(LutrisError):
    """Raised when authentication to a service fails"""


class UnavailableGameError(LutrisError):
    """Raised when a game is unavailable from a service"""


class UnavailableLibrariesError(MisconfigurationError):
    def __init__(self, libraries, arch=None):
        message = _(
            "The following {arch} libraries are required but are not installed on your system:\n{libs}"
        ).format(
            arch=arch if arch else "",
            libs=", ".join(libraries)
        )
        super().__init__(message)
        self.libraries = libraries


class UnavailableRunnerError(MisconfigurationError):
    """Raised when a runner is not installed or not installed fully."""


class UnspecifiedVersionError(MisconfigurationError):
    """Raised when a version number must be specified, but was not."""


class MissingExecutableError(MisconfigurationError):
    """Raised when a program can't be located."""


class EsyncLimitError(Exception):
    """Raised when the ESYNC limit is not set correctly."""


class FsyncUnsupportedError(Exception):
    """Raised when FSYNC is enabled, but is not supported by the kernel."""


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


def _handle_callback_error(error_objects, error):
    first_toplevel = None

    for error_object in error_objects:
        if not error_object:
            continue

        if error_object and hasattr(error_object, "on_watched_error"):
            error_object.on_watched_error(error)
            return

        if error_object and hasattr(error_object, "get_toplevel"):
            toplevel = error_object.get_toplevel()
        else:
            toplevel = None

        if toplevel and hasattr(toplevel, "on_watched_error"):
            toplevel.on_watched_error(error)
            return

        if not first_toplevel:
            first_toplevel = toplevel

    ErrorDialog(error, parent=first_toplevel)
    return


def _error_handling_connect(self: Gtk.Widget, signal_spec: str, handler, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as ex:
            logger.exception("Error handling signal '%s': %s", signal_spec, ex)

            error_objects = [handler.__self__, self] if hasattr(handler, "__self__") else [self]
            _handle_callback_error(error_objects, ex)
            return None

    return _original_connect(self, signal_spec, wrapper, *args, **kwargs)


def _error_handling_add_emission_hook(emitting_type, signal_spec, handler, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as ex:
            logger.exception("Error handling emission hook '%s.%s': %s", emitting_type, signal_spec, ex)
            error_objects = [handler.__self__] if hasattr(handler, "__self__") else []
            _handle_callback_error(error_objects, ex)
            return True

    return _original_add_emission_hook(emitting_type, signal_spec, wrapper, *args, **kwargs)


def _error_handling_idle_add(handler, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as ex:
            logger.exception("Error handling idle function: %s", ex)
            error_objects = [handler.__self__] if hasattr(handler, "__self__") else []
            _handle_callback_error(error_objects, ex)
            return False

    return _original_idle_add(wrapper, *args, **kwargs)


def _error_handling_timeout_add(interval, handler, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as ex:
            logger.exception("Error handling timeout function: %s", ex)
            error_objects = [handler.__self__] if hasattr(handler, "__self__") else []
            _handle_callback_error(error_objects, ex)
            return False

    return _original_timeout_add(interval, wrapper, *args, **kwargs)


# TODO: explicit init call is probably safer
_original_connect = Gtk.Widget.connect
GObject.Object.connect = _error_handling_connect

_original_add_emission_hook = GObject.add_emission_hook
GObject.add_emission_hook = _error_handling_add_emission_hook

_original_idle_add = GLib.idle_add
GLib.idle_add = _error_handling_idle_add

_original_timeout_add = GLib.timeout_add
GLib.timeout_add = _error_handling_timeout_add
