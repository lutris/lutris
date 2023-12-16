"""Exception handling module"""
from functools import wraps
from gettext import gettext as _
from typing import Any, Callable, Iterable

from gi.repository import Gio, GLib, GObject, Gtk

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


def _get_error_parent(error_objects: Iterable) -> Gtk.Window:
    """Obtains a top-level window to use as the parent of an
    error, by examining s list of objects. Any that are None
    are skipped; we call get_toplevel() on each object that has
    this method, and return the first non-None result.

    If this fails, we turn to the application's main window instead."""

    for error_object in error_objects:
        if not error_object:
            continue

        if error_object and hasattr(error_object, "get_toplevel"):
            toplevel = error_object.get_toplevel()
            if toplevel:
                return toplevel

    application = Gio.Application.get_default()
    return application.window if application else None


def _create_error_wrapper(handler: Callable, handler_name: str,
                          error_result: Any,
                          error_method_name: str,
                          connected_object: Any = None):
    """Wraps a handler function in an error handler that will log and then report
    any exceptions, then return the 'error_result'."""

    handler_object = handler.__self__ if hasattr(handler, "__self__") else None

    def error_wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as ex:
            logger.exception("Error handling %s: %s", handler_name, ex)

            if handler_object and hasattr(handler_object, error_method_name):
                error_method = getattr(handler_object, error_method_name)
                error_method(ex)
            else:
                ErrorDialog(ex, parent=_get_error_parent([handler_object, connected_object]))
            return error_result

    return error_wrapper


def init_exception_backstops():
    """This function is called once only, during startup, and replaces ("swizzles") a bunch of
    callback setup functions in GLib. The callbacks are all wrapped with error handlers that
    log the error and report it.

    This is important to do because PyGObject will straight up crash if an exception escapes
    these handlers; it's better to tell the user and try to survive.

    You can provide certain methods to provide error handling, but if you do not you get an
    ErrorDialog. Put these handling methods on the same object as the callback method itself.

    We take care of these methods:
        GObject.Object.connect (via on_signal_error(self, error))
        GObject.add_emission_hook (via on_emission_hook_error(self, error))
        GLib.idle_add (via on_idle_error(self, error))
        GLib.timeout_add (via on_timeout_error(self, error))

    Idle and timeout handlers will be disconnected if this happens to avoid repeated error reports,
    but signals and emission hooks will remain connected.
    """

    def _error_handling_connect(self: Gtk.Widget, signal_spec: str, handler, *args, **kwargs):
        error_wrapper = _create_error_wrapper(handler, f"signal '{signal_spec}'",
                                              error_result=None,
                                              error_method_name="on_signal_error",
                                              connected_object=self)
        return _original_connect(self, signal_spec, error_wrapper, *args, **kwargs)

    def _error_handling_add_emission_hook(emitting_type, signal_spec, handler, *args, **kwargs):
        error_wrapper = _create_error_wrapper(handler, f"emission hook '{emitting_type}.{signal_spec}'",
                                              error_result=True,  # stay attached
                                              error_method_name="on_emission_hook_error")
        return _original_add_emission_hook(emitting_type, signal_spec, error_wrapper, *args, **kwargs)

    def _error_handling_idle_add(handler, *args, **kwargs):
        error_wrapper = _create_error_wrapper(handler, "idle function",
                                              error_result=False,  # stop calling idle func
                                              error_method_name="on_idle_error")
        return _original_idle_add(error_wrapper, *args, **kwargs)

    def _error_handling_timeout_add(interval, handler, *args, **kwargs):
        error_wrapper = _create_error_wrapper(handler, "timeout function",
                                              error_result=False,  # stop calling timeout fund
                                              error_method_name="on_timeout_error")
        return _original_timeout_add(interval, error_wrapper, *args, **kwargs)

    _original_connect = Gtk.Widget.connect
    GObject.Object.connect = _error_handling_connect

    _original_add_emission_hook = GObject.add_emission_hook
    GObject.add_emission_hook = _error_handling_add_emission_hook

    _original_idle_add = GLib.idle_add
    GLib.idle_add = _error_handling_idle_add

    _original_timeout_add = GLib.timeout_add
    GLib.timeout_add = _error_handling_timeout_add
