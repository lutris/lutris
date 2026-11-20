"""Reports errors that escape GTK and GLib callbacks, instead of letting them crash Lutris"""

import sys
from collections.abc import Callable, Iterable
from typing import Any, cast

from gi.repository import GLib, GObject, Gtk

from lutris.gui.dialogs import ErrorDialog, display_error
from lutris.gui.widgets.utils import get_required_main_window
from lutris.installer.errors import ScriptingError
from lutris.util.log import logger
from lutris.util.strings import gtk_safe

AnyCallable = Callable[..., Any]


def _show_uncaught_scripting_errors() -> None:
    """Show an installer script's errors in a dialog when nothing else caught them."""
    original_excepthook = sys.excepthook

    def excepthook(error_type, value, traceback):
        if error_type == ScriptingError:
            message = value.message
            if value.faulty_data:
                message += "\n<b>%s</b>" % gtk_safe(value.faulty_data)
            ErrorDialog(message)
        else:
            original_excepthook(error_type, value, traceback)

    sys.excepthook = excepthook


def _get_error_parent(error_objects: Iterable[Any]) -> Gtk.Window:
    """Obtains a top-level window to use as the parent of an
    error, by examining s list of objects. Any that are None
    are skipped; we call get_toplevel() on each object that has
    this method, and return the first non-None result.

    If this fails, we turn to the application's main window instead."""

    for error_object in error_objects:
        if not error_object:
            continue

        try:
            if error_object and hasattr(error_object, "get_toplevel"):
                toplevel: Gtk.Window = error_object.get_toplevel()
                if toplevel:
                    return toplevel
        except GLib.GError:
            pass  # hasattr() is always true for (some) GObjects, but the method fails when used

    return get_required_main_window()


def _create_error_wrapper(
    handler: AnyCallable, handler_name: str, error_result: Any, error_method_name: str, connected_object: Any = None
) -> AnyCallable:
    """Wraps a handler function in an error handler that will log and then report
    any exceptions, then return the 'error_result'."""

    handler_object = handler.__self__ if hasattr(handler, "__self__") else None

    def error_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return handler(*args, **kwargs)
        except Exception as ex:
            logger.exception("Error handling %s: %s", handler_name, ex)

            if handler_object and hasattr(handler_object, error_method_name):
                error_method = getattr(handler_object, error_method_name)
                error_method(ex)
            else:
                display_error(ex, _get_error_parent([handler_object, connected_object]))
            return error_result

    return cast(AnyCallable, error_wrapper)


def init_exception_backstops() -> None:
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

    It also shows installer script errors (ScriptingError) that nothing else caught.
    """

    def _error_handling_connect(
        self: Gtk.Widget, signal_spec: str, handler: AnyCallable, *args: Any, **kwargs: Any
    ) -> Any:
        error_wrapper = _create_error_wrapper(
            handler,
            f"signal '{signal_spec}'",
            error_result=None,
            error_method_name="on_signal_error",
            connected_object=self,
        )
        return _original_connect(self, signal_spec, error_wrapper, *args, **kwargs)

    def _error_handling_add_emission_hook(
        emitting_type: GObject.Object, signal_spec: str, handler: AnyCallable, *args: Any, **kwargs: Any
    ) -> Any:
        error_wrapper = _create_error_wrapper(
            handler,
            f"emission hook '{emitting_type}.{signal_spec}'",
            error_result=True,  # stay attached
            error_method_name="on_emission_hook_error",
        )
        return _original_add_emission_hook(emitting_type, signal_spec, error_wrapper, *args, **kwargs)

    def _error_handling_idle_add(handler: AnyCallable, *args: Any, **kwargs: Any) -> Any:
        error_wrapper = _create_error_wrapper(
            handler,
            "idle function",
            error_result=False,  # stop calling idle func
            error_method_name="on_idle_error",
        )
        return _original_idle_add(error_wrapper, *args, **kwargs)

    def _error_handling_timeout_add(interval: int, handler: AnyCallable, *args: Any, **kwargs: Any) -> Any:
        error_wrapper = _create_error_wrapper(
            handler,
            "timeout function",
            error_result=False,  # stop calling timeout fund
            error_method_name="on_timeout_error",
        )
        return _original_timeout_add(interval, error_wrapper, *args, **kwargs)

    _original_connect = Gtk.Widget.connect
    GObject.Object.connect = _error_handling_connect

    _original_add_emission_hook: Callable[[GObject.Object, str, AnyCallable], Any] = GObject.add_emission_hook
    GObject.add_emission_hook = _error_handling_add_emission_hook  # type: ignore[misc]

    _original_idle_add = GLib.idle_add
    GLib.idle_add = _error_handling_idle_add

    _original_timeout_add = GLib.timeout_add
    GLib.timeout_add = _error_handling_timeout_add

    _show_uncaught_scripting_errors()
