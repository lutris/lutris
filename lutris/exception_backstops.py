import asyncio
from asyncio import Task, iscoroutine
from functools import wraps
from typing import Any, Callable, Iterable

from gi.repository import Gio, GLib, GObject, Gtk

from lutris.gui.dialogs import ErrorDialog
from lutris.util.jobs import get_main_loop
from lutris.util.log import logger


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


def async_execute(coroutine, error_objects: Iterable = None) -> Task:
    """This schedules the co-routine given (creating a task), but adds error handling
    like we use for callbacks. The 'error_objects', if provided, are searched for
    a widget that can provide a top-level for the error dialog."""

    def on_future_error(fut):
        if not fut.cancelled():
            err = fut.exception()
            if err:
                _handle_error(err,
                              handler_name=f"function '{coroutine.__name__}'",
                              error_objects=error_objects)

    task = get_main_loop().create_task(coroutine)
    task.add_done_callback(on_future_error)
    return task


def create_callback_error_wrapper(handler: Callable, handler_name: str,
                                  error_result: Any,
                                  async_result: Any,
                                  error_method_name: str = None,
                                  error_objects: Iterable = None):
    """Wraps a handler function in an error handler that will log and then report
    any exceptions, then return the 'error_result'. If the handler returns a co-routine
    we schedule it, and then this function returns 'async_result'.

    'handler_name' is incorporated in the log message.

    This will try to use the method named by 'error_method_name' on the target of the handler,
    if given, and if then it will search the 'error_objects' until it finds the method. If
    it never does, it shows n ErrorDialog. These same objects can provide the top-level for
    the ErrorDialog's parent.
    """
    error_objects = list(error_objects) if error_objects else []

    def on_error(error):
        err_objs = error_objects
        if hasattr(handler, "__self__"):
            handler_object = handler.__self__
            if handler_object:
                err_objs = [handler_object] + err_objs

        _handle_error(error,
                      handler_name=handler_name,
                      error_method_name=error_method_name,
                      error_objects=err_objs)

    def on_future_error(fut):
        err = fut.exception()
        if err:
            on_error(err)

    def error_wrapper(*args, **kwargs) -> Any:
        try:
            result = handler(*args, **kwargs)
            if iscoroutine(result):
                task = asyncio.create_task(result)
                task.add_done_callback(on_future_error)
                return async_result
            return result
        except Exception as ex:
            on_error(ex)
            return error_result

    return error_wrapper


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


def _handle_error(error: Exception, handler_name: str, error_method_name: str = None,
                  error_objects: Iterable = None) -> None:
    logger.exception("Error handling %s: %s", handler_name, error)

    if error_method_name and error_objects:
        for error_object in error_objects:
            if error_object and hasattr(error_object, error_method_name):
                error_method = getattr(error_object, error_method_name)
                error_method(error)
                return

    ErrorDialog(error, parent=_get_error_parent(error_objects or []))


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

    def _error_handling_connect(self: Gtk.Widget, signal_spec: str, handler, *args,
                                error_result=None, async_result=None,
                                **kwargs):
        error_wrapper = create_callback_error_wrapper(handler, f"signal '{signal_spec}'",
                                                      error_result=error_result,
                                                      async_result=async_result,
                                                      error_method_name="on_signal_error",
                                                      error_objects=[self])
        return _original_connect(self, signal_spec, error_wrapper, *args, **kwargs)

    def _error_handling_add_emission_hook(emitting_type, signal_spec, handler, *args,
                                          error_result=True, async_result=True,
                                          **kwargs):
        error_wrapper = create_callback_error_wrapper(handler, f"emission hook '{emitting_type}.{signal_spec}'",
                                                      error_result=error_result,
                                                      async_result=async_result,
                                                      error_method_name="on_emission_hook_error")
        return _original_add_emission_hook(emitting_type, signal_spec, error_wrapper, *args, **kwargs)

    def _error_handling_idle_add(handler, *args, error_result=False, async_result=False, **kwargs):
        error_wrapper = create_callback_error_wrapper(handler, "idle function",
                                                      error_result=error_result,
                                                      async_result=async_result,
                                                      error_method_name="on_idle_error")
        return _original_idle_add(error_wrapper, *args, **kwargs)

    def _error_handling_timeout_add(interval, handler, *args, error_result=False, async_result=False, **kwargs):
        error_wrapper = create_callback_error_wrapper(handler, "timeout function",
                                                      error_result=error_result,
                                                      async_result=async_result,
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
