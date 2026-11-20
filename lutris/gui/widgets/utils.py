"""Various utilities using the GObject framework"""

import os
from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeVar, cast

import cairo
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from lutris import settings
from lutris.exceptions import MissingMediaError
from lutris.util import system
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication
    from lutris.gui.lutriswindow import LutrisWindow


def check_pixbuf_formats() -> None:
    """Log an error for each image format Lutris shows that GdkPixbuf can't load."""
    format_names = [f.get_name() for f in GdkPixbuf.Pixbuf.get_formats()]
    for required in ("svg", "png", "jpeg"):
        if required not in format_names:
            logger.error("'%s' PixBuf support is not installed.", required.upper())


def get_application() -> "LutrisApplication | None":
    return cast("LutrisApplication", Gio.Application.get_default())


def get_required_application() -> "LutrisApplication":
    application = cast("LutrisApplication", Gio.Application.get_default())
    if not application:
        raise RuntimeError("The LutrisApplication does not exist.")
    return application


def get_main_window() -> "LutrisWindow | None":
    """Return the application's main window, or None if it doesn't exist
    (though it almost alway does exist)"""
    application = get_application()
    return application.window if application else None


def get_required_main_window() -> "LutrisWindow":
    """Return the application's main window or raises an exception if
    it doesn't exist."""
    application = get_required_application()
    window = application.window
    if not window:
        raise RuntimeError("The main window does not exist.")
    return window


def get_widget_window(widget: Gtk.Widget | None) -> Gtk.Window | None:
    """Returns the window that contains a widget, if any. This wll return None
    for a widget that is not in a window, rather than returning the widget itself
    like get_toplevel()."""
    if widget:
        return cast(Gtk.Window, widget.get_ancestor(Gtk.Window))
    else:
        return None


def set_cursor_by_name(widget: Gtk.Widget, name: str | None) -> None:
    """Applies the named cursor to a widget; if 'name' is None the widget reverts to
    its default cursor. Does nothing if the widget has not been realized, or if the cursor
    theme in use has no cursor of that name; Gdk.Cursor.new_from_name() returns NULL then,
    which PyGObject reports as a TypeError."""
    gdk_window = widget.get_window()
    if not gdk_window:
        return

    cursor = None
    if name:
        try:
            cursor = Gdk.Cursor.new_from_name(widget.get_display(), name)
        except TypeError:
            logger.warning("The cursor '%s' is not available in the current cursor theme.", name)
            return

    gdk_window.set_cursor(cursor)


TChildWidget = TypeVar("TChildWidget", bound=Gtk.Widget)


def get_widget_children(widget: Gtk.Widget | None, child_type: type[TChildWidget] | None = None) -> list[TChildWidget]:
    """Returns the children of any widget; non-containers have no children
    and returns an empty list. This can filter out a specific type of child widget if child_type
    is not None, but otherwise it returns all children."""
    if isinstance(widget, Gtk.Container):
        if child_type:
            return [w for w in widget.get_children() if isinstance(w, child_type)]
        else:
            return list(cast(Iterable[TChildWidget], widget.get_children()))
    else:
        return []


def open_uri(uri: str) -> None:
    """Opens a local or remote URI with the default application"""
    system.spawn(["xdg-open", uri])


def get_surface_size(surface: cairo.ImageSurface) -> tuple[float, float]:
    """Returns the size of a surface, accounting for the device scale;
    the surface's get_width() and get_height() are in physical pixels."""
    device_scale_x, device_scale_y = surface.get_device_scale()
    width = surface.get_width() / device_scale_x
    height = surface.get_height() / device_scale_y
    return width, height


def get_scaled_surface_by_path(
    path: str, size: tuple[float, float], device_scale: float, preserve_aspect_ratio: bool = True
) -> cairo.ImageSurface | None:
    """Returns a Cairo surface containing the image at the path given. It has the size indicated.

    You specify the device_scale, and the bitmap is generated at an enlarged size accordingly,
    but with the device scale of the surface also set; in this way a high-DPI image can be
    rendered conveniently.

    If you pass True for preserve_aspect_ratio, the aspect ratio of the image is preserved,
    but will be no larger than the size (times the device_scale).

    If there's no file at the path, or it is empty, this function returns None.
    """
    pixbuf = get_pixbuf_by_path(path)
    if not pixbuf:
        return None

    pixbuf_width = pixbuf.get_width()
    pixbuf_height = pixbuf.get_height()

    scale_x = (size[0] / pixbuf_width) * device_scale
    scale_y = (size[1] / pixbuf_height) * device_scale

    if preserve_aspect_ratio:
        scale_x = min(scale_x, scale_y)
        scale_y = scale_x

    pixel_width = round(pixbuf_width * scale_x)
    pixel_height = round(pixbuf_height * scale_y)

    surface = cairo.ImageSurface(cairo.Format.ARGB32, pixel_width, pixel_height)  # pylint:disable=no-member
    cr = cairo.Context(surface)  # pylint:disable=no-member
    cr.scale(scale_x, scale_y)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.get_source().set_extend(cairo.Extend.PAD)  # pylint: disable=no-member
    cr.paint()
    surface.set_device_scale(device_scale, device_scale)
    return surface


def get_pixbuf_by_path(
    path: str, size: tuple[int, int] | None = None, preserve_aspect_ratio: bool = True
) -> GdkPixbuf.Pixbuf | None:
    """Reads an image file and returns the pixbuf. If you provide a size, this scales
    the file to fit that size, preserving the aspect ratio if preserve_aspect_ratio is
    True. If the file is missing or empty, or if 'path' is None or empty,
    this returns None. Still raises GLib.GError for corrupt files."""
    if not system.path_exists(path, exclude_empty=True):
        return None

    if size:
        # new_from_file_at_size scales but preserves aspect ratio
        width, height = size
        if preserve_aspect_ratio:
            return GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)

        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width, height, preserve_aspect_ratio=False)

    return GdkPixbuf.Pixbuf.new_from_file(path)


def get_required_pixbuf_by_path(
    path: str, size: tuple[int, int] | None = None, preserve_aspect_ratio: bool = True
) -> GdkPixbuf.Pixbuf:
    """Reads an image file and returns the pixbuf. If you provide a size, this scales
    the file to fit that size, preserving the aspect ratio if preserve_aspect_ratio is
    True. If the file is missing or unreadable, or if 'path' is None or empty, this raises
    MissingMediaError."""
    try:
        pixbuf = get_pixbuf_by_path(path, size, preserve_aspect_ratio)
        if not pixbuf:
            raise MissingMediaError(filename=path)
        return pixbuf
    except GLib.GError as ex:
        logger.exception("Unable to load icon from image %s", path)
        raise MissingMediaError(message=str(ex), filename=path) from ex


def has_stock_icon(name: str) -> bool:
    """This tests if a GTK stock icon is known; if not we can try a fallback."""
    if not name:
        return False

    theme = Gtk.IconTheme.get_default()
    return theme.has_icon(name)


def pick_stock_icon(names: str | Iterable[str], fallback_name: str = "package-x-generic-symbolic") -> str:
    """Used to select a stock icon that actually exists in the icon set; it tries all the names given,
    and returns the first where has_stock_icon is true. If none pass the test, returns fallback_name instead."""
    if isinstance(names, str):
        names = [names]

    for name in names:
        if has_stock_icon(name):
            return name

    return fallback_name


def load_icon_theme() -> None:
    """Add the lutris icon folder to the default theme"""
    icon_theme = Gtk.IconTheme.get_default()
    local_theme_path = os.path.join(settings.RUNTIME_DIR, "icons")
    if local_theme_path not in icon_theme.get_search_path():
        icon_theme.prepend_search_path(local_theme_path)
