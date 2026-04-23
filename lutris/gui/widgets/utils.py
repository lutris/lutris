"""Various utilities using the GObject framework"""

import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from lutris import settings
from lutris.exceptions import MissingMediaError
from lutris.gui.widgets import NotificationSource
from lutris.util import datapath, magic, system
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication
    from lutris.gui.lutriswindow import LutrisWindow

try:
    from PIL import Image
except ImportError:
    Image = None

ICON_SIZE = (32, 32)
BANNER_SIZE = (184, 69)
MEDIA_CACHE_INVALIDATED = NotificationSource()


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


TChildWidget = TypeVar("TChildWidget", bound=Gtk.Widget)


def get_widget_children(widget: Gtk.Widget | None, child_type: type[TChildWidget] | None = None) -> list[TChildWidget]:
    """Returns the children of any widget by iterating with get_first_child()/get_next_sibling().
    This can filter out a specific type of child widget if child_type
    is not None, but otherwise it returns all children."""
    if widget is None:
        return []
    children: list[TChildWidget] = []
    child = widget.get_first_child()
    while child is not None:
        if child_type is None or isinstance(child, child_type):
            children.append(cast(TChildWidget, child))
        child = child.get_next_sibling()
    return children


def open_uri(uri: str) -> None:
    """Opens a local or remote URI with the default application"""
    system.spawn(["xdg-open", uri])


def get_image_file_extension(path: str) -> str | None:
    """Returns the canonical file extension for an image,
    either 'jpg' or 'png'; we deduce this from the file extension, or if that fails the
    file's 'magic' prefix bytes."""
    ext = os.path.splitext(path)[1].casefold()
    if ext in [".jpg", ".jpeg"]:
        return ".jpg"
    if ext == ".png":
        return ".png"

    try:
        file_type = magic.from_file(path).casefold()
    except OSError:
        return None  # file is missing, or can't read it

    if "jpeg image data" in file_type:
        return ".jpg"
    if "png image data" in file_type:
        return ".png"

    return None


@dataclass(init=False, slots=True)
class ScaledTexture:
    """A pixbuf scaled to fit a target size at a given device scale, uploaded
    to the GPU as a ``Gdk.Texture``.

    ``corner_is_bright`` is True when the bottom-right corner region of the
    scaled pixbuf has all RGB(A) channels at 128 or above at the sampled
    pixels; callers use it to pick badge contrast colours. It is always False
    when the caller does not supply a ``corner_size_physical``.
    """

    texture: Gdk.Texture
    logical_size: tuple[float, float]
    corner_is_bright: bool

    def __init__(
        self,
        pixbuf: GdkPixbuf.Pixbuf,
        size: tuple[float, float],
        device_scale: float,
        preserve_aspect_ratio: bool = True,
        corner_size_physical: tuple[int, int] | None = None,
    ) -> None:
        pixbuf_width = pixbuf.get_width()
        pixbuf_height = pixbuf.get_height()

        scale_x = (size[0] / pixbuf_width) * device_scale
        scale_y = (size[1] / pixbuf_height) * device_scale

        if preserve_aspect_ratio:
            scale_x = min(scale_x, scale_y)
            scale_y = scale_x

        pixel_width = max(1, round(pixbuf_width * scale_x))
        pixel_height = max(1, round(pixbuf_height * scale_y))

        if pixel_width != pixbuf_width or pixel_height != pixbuf_height:
            scaled = pixbuf.scale_simple(pixel_width, pixel_height, GdkPixbuf.InterpType.BILINEAR)
            if scaled is None:
                raise RuntimeError(f"Unable to scale pixbuf to {pixel_width}x{pixel_height}")
        else:
            scaled = pixbuf

        corner_is_bright = False
        if corner_size_physical and corner_size_physical[0] > 0 and corner_size_physical[1] > 0:
            corner_is_bright = self._is_bright_pixbuf_corner(scaled, corner_size_physical)

        self.texture = Gdk.Texture.new_for_pixbuf(scaled)
        self.logical_size = (pixel_width / device_scale, pixel_height / device_scale)
        self.corner_is_bright = corner_is_bright

    @classmethod
    def from_path(
        cls,
        path: str,
        size: tuple[float, float],
        device_scale: float,
        preserve_aspect_ratio: bool = True,
        corner_size_physical: tuple[int, int] | None = None,
    ) -> "ScaledTexture | None":
        """Load an image file and return it as a ``ScaledTexture`` fitted to
        ``size`` at ``device_scale``. Returns ``None`` if the file is missing or
        the pixbuf can't be loaded; raises if scaling fails."""
        pixbuf = get_pixbuf_by_path(path)
        if not pixbuf:
            return None
        return cls(pixbuf, size, device_scale, preserve_aspect_ratio, corner_size_physical)

    @staticmethod
    def _is_bright_pixbuf_corner(pixbuf: GdkPixbuf.Pixbuf, corner_size: tuple[int, int]) -> bool:
        """Tests four pixels in the bottom-right corner region of the pixbuf. Returns True if
        all sampled pixels have every colour channel (and alpha, if present) at 128 or above.
        This matches the surface-based heuristic previously used for badge contrast."""
        corner_w, corner_h = corner_size
        pixel_w = pixbuf.get_width()
        pixel_h = pixbuf.get_height()
        n_channels = pixbuf.get_n_channels()
        rowstride = pixbuf.get_rowstride()
        data = pixbuf.get_pixels()

        # Clamp number of channels to at most 4 (RGB or RGBA). Pixbufs are 8 bits per sample.
        check_channels = min(n_channels, 4)

        def is_bright(x: int, y: int) -> bool:
            if not (0 <= x < pixel_w and 0 <= y < pixel_h):
                return False
            offset = y * rowstride + x * n_channels
            for i in range(check_channels):
                if data[offset + i] < 128:
                    return False
            return True

        return (
            is_bright(pixel_w - 1, pixel_h - 1)
            and is_bright(pixel_w - corner_w, pixel_h - 1)
            and is_bright(pixel_w - 1, pixel_h - corner_h)
            and is_bright(pixel_w - corner_w, pixel_h - corner_h)
        )


def get_default_icon_path(size: tuple[int, int]) -> str:
    """Returns the path to the default icon for the size given; it's
    a Lutris icon for a square size, and a gradient for other sizes."""
    if not size or size[0] == size[1]:
        filename = "media/default_icon.png"
    else:
        filename = "media/default_banner.png"
    return os.path.join(datapath.get(), filename)


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

    display = Gdk.Display.get_default()
    if not display:
        return False
    theme = Gtk.IconTheme.get_for_display(display)
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


def get_runtime_icon_path(icon_name: str) -> str | None:
    """Finds the icon file for an icon whose name is given; this searches the icons
    in Lutris's runtime directory. The name is normalized by removing spaces
    and lower-casing it, and both .png and .svg files with the name can be found.

    Arguments:
    icon_name -- The name of the icon to retrieve

    Returns:
        The path to the icon, or None if it wasn't found.
    """
    filename = icon_name.lower().replace(" ", "")
    # We prefer bitmaps over SVG, because we've got some SVG icons with the
    # wrong size (oops) and this avoids them.
    search_directories = [
        "icons/hicolor/64x64/apps",
        "icons/hicolor/24x24/apps",
        "icons",
        "icons/hicolor/scalable/apps",
        "icons/hicolor/symbolic/apps",
    ]
    extensions = [".png", ".svg"]
    for search_dir in search_directories:
        for ext in extensions:
            icon_path = os.path.join(settings.RUNTIME_DIR, search_dir, filename + ext)
            if os.path.exists(icon_path):
                return icon_path
    return None


def get_runtime_icon_image(icon_name: str, fallback_stock_icon_name: str | None = None) -> Gtk.Image:
    """Returns a Gtk.Image of an icon for a runtime or service; the image has the
    default icon size. If the icon can't be found, we'll fall back onto another,
    stock icon. If you don't supply one (or it's not available) we'll fall back
    further to 'package-x-generic-symbolic'; we always give you something."""
    path = get_runtime_icon_path(icon_name)
    if path:
        pixbuf = get_pixbuf_by_path(path, ICON_SIZE)
        if pixbuf:
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            icon = Gtk.Image.new_from_paintable(texture)
            icon.set_pixel_size(ICON_SIZE[0])
            return icon

    if not fallback_stock_icon_name or not has_stock_icon(fallback_stock_icon_name):
        fallback_stock_icon_name = "package-x-generic-symbolic"

    icon = Gtk.Image.new_from_icon_name(fallback_stock_icon_name)
    icon.set_icon_size(Gtk.IconSize.LARGE)
    return icon


def thumbnail_image(base_image: "Image.Image", target_size: tuple[int, int]) -> "Image.Image":
    base_width, base_height = base_image.size
    base_ratio = base_width / base_height
    target_width, target_height = target_size
    target_ratio = target_width / target_height

    # Resize and crop coverart
    if base_ratio >= target_ratio:
        width = int(base_width * (target_height / base_height))
        height = target_height
    else:
        width = target_width
        height = int(base_height * (target_width / base_width))
    x_offset = int((width - target_width) / 2)
    y_offset = int((height - target_height) / 2)
    base_image = base_image.resize((width, height), resample=Image.Resampling.BICUBIC)
    base_image = base_image.crop((x_offset, y_offset, width - x_offset, height - y_offset))
    return base_image


def paste_overlay(base_image: "Image.Image", overlay_image: "Image.Image", position: float = 0.7) -> "Image.Image":
    base_width, base_height = base_image.size
    overlay_width, overlay_height = overlay_image.size
    offset_x = int((base_width - overlay_width) / 2)
    offset_y = int((base_height - overlay_height) / 2)
    base_image.paste(
        overlay_image, (offset_x, offset_y, overlay_width + offset_x, overlay_height + offset_y), mask=overlay_image
    )
    return base_image


def load_icon_theme() -> None:
    """Add the lutris icon folder to the default theme"""
    display = Gdk.Display.get_default()
    if not display:
        return
    icon_theme = Gtk.IconTheme.get_for_display(display)
    local_theme_path = os.path.join(settings.RUNTIME_DIR, "icons")
    search_path = icon_theme.get_search_path()
    if not search_path or local_theme_path not in search_path:
        icon_theme.add_search_path(local_theme_path)
