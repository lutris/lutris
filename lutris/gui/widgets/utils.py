"""Various utilities using the GObject framework"""

import array
import os
from typing import Optional

import cairo
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from lutris import settings
from lutris.exceptions import MissingMediaError
from lutris.gui.widgets import NotificationSource
from lutris.util import datapath, magic, system
from lutris.util.log import logger

try:
    from PIL import Image
except ImportError:
    Image = None

ICON_SIZE = (32, 32)
BANNER_SIZE = (184, 69)
MEDIA_CACHE_INVALIDATED = NotificationSource()


def get_main_window(widget):
    """Return the application's main window from one of its widget"""
    parent = widget.get_toplevel()
    if not isinstance(parent, Gtk.Window):
        # The sync dialog may have closed
        parent = Gio.Application.get_default().props.active_window
    for window in parent.application.get_windows():
        if "LutrisWindow" in window.__class__.__name__:
            return window
    return


def open_uri(uri):
    """Opens a local or remote URI with the default application"""
    system.spawn(["xdg-open", uri])


def get_image_file_extension(path: str) -> Optional[str]:
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


def get_surface_size(surface):
    """Returns the size of a surface, accounting for the device scale;
    the surface's get_width() and get_height() are in physical pixels."""
    device_scale_x, device_scale_y = surface.get_device_scale()
    width = surface.get_width() / device_scale_x
    height = surface.get_height() / device_scale_y
    return width, height


def get_scaled_surface_by_path(path, size, device_scale, preserve_aspect_ratio=True):
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

    pixel_width = int(round(pixbuf_width * scale_x))
    pixel_height = int(round(pixbuf_height * scale_y))

    surface = cairo.ImageSurface(cairo.Format.ARGB32, pixel_width, pixel_height)  # pylint:disable=no-member
    cr = cairo.Context(surface)  # pylint:disable=no-member
    cr.scale(scale_x, scale_y)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.get_source().set_extend(cairo.Extend.PAD)  # pylint: disable=no-member
    cr.paint()
    surface.set_device_scale(device_scale, device_scale)
    return surface


def get_default_icon_path(size):
    """Returns the path to the default icon for the size given; it's
    a Lutris icon for a square size, and a gradient for other sizes."""
    if not size or size[0] == size[1]:
        filename = "media/default_icon.png"
    else:
        filename = "media/default_banner.png"
    return os.path.join(datapath.get(), filename)


def get_pixbuf_by_path(path, size=None, preserve_aspect_ratio=True):
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


def get_required_pixbuf_by_path(path, size=None, preserve_aspect_ratio=True):
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


def has_stock_icon(name):
    """This tests if a GTK stock icon is known; if not we can try a fallback."""
    if not name:
        return False

    theme = Gtk.IconTheme.get_default()
    return theme.has_icon(name)


def get_runtime_icon_path(icon_name):
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


def convert_to_background(background_path, target_size=(320, 1080)):
    """Converts an image to a pane background"""
    coverart = Image.open(background_path)
    coverart = coverart.convert("RGBA")

    target_width, target_height = target_size
    image_height = int(target_height * 0.80)  # 80% of the mask is visible
    orig_width, orig_height = coverart.size

    # Resize and crop coverart
    width = int(orig_width * (image_height / orig_height))
    offset = int((width - target_width) / 2)
    coverart = coverart.resize((width, image_height), resample=Image.Resampling.BICUBIC)
    coverart = coverart.crop((offset, 0, target_width + offset, image_height))

    # Resize canvas of coverart by putting transparent pixels on the bottom
    coverart_bg = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    coverart_bg.paste(coverart, (0, 0, target_width, image_height))

    # Apply a tint to the base image
    # tint = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 255))
    # coverart = Image.blend(coverart, tint, 0.6)

    # Paste coverart on transparent image while applying a gradient mask
    background = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    mask = Image.open(os.path.join(datapath.get(), "media/mask.png"))
    background.paste(coverart_bg, mask=mask)

    return background


def thumbnail_image(base_image, target_size):
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


def paste_overlay(base_image, overlay_image, position=0.7):
    base_width, base_height = base_image.size
    overlay_width, overlay_height = overlay_image.size
    offset_x = int((base_width - overlay_width) / 2)
    offset_y = int((base_height - overlay_height) / 2)
    base_image.paste(
        overlay_image, (offset_x, offset_y, overlay_width + offset_x, overlay_height + offset_y), mask=overlay_image
    )
    return base_image


def image2pixbuf(image):
    """Converts a PIL Image to a GDK Pixbuf"""
    image_array = array.array("B", image.tobytes())
    width, height = image.size
    return GdkPixbuf.Pixbuf.new_from_data(image_array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4)


def load_icon_theme():
    """Add the lutris icon folder to the default theme"""
    icon_theme = Gtk.IconTheme.get_default()
    local_theme_path = os.path.join(settings.RUNTIME_DIR, "icons")
    if local_theme_path not in icon_theme.get_search_path():
        icon_theme.prepend_search_path(local_theme_path)
