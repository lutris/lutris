"""Various utilities using the GObject framework"""
import array
import os
from functools import lru_cache

from gi.repository import GdkPixbuf, Gio, GLib, Gtk

from lutris import settings
from lutris.util import datapath, system, magic
from lutris.util.log import logger

try:
    from PIL import Image
except ImportError:
    Image = None

ICON_SIZE = (32, 32)
BANNER_SIZE = (184, 69)


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


def get_image_file_format(path):
    """Returns the file format fo an image, either 'jpeg' or 'png';
    we deduce this from the file extension, or if that fails the
    file's 'magic' prefix bytes."""
    ext = os.path.splitext(path)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        return "jpeg"
    if path == ".png":
        return "png"

    file_type = magic.from_file(path).lower()
    if "jpeg image data" in file_type:
        return "jpeg"
    if "png image data" in file_type:
        return "png"

    return None


def get_pixbuf(path, size):
    """Return a pixbuf from file `image` at `size`, preserving its aspect ratio.
    If the file is not found or can't be decoded, this will return the default
    icon. If 'size' square, this is a Lutris icon; if not it is a gradient filling
    the full size given."""
    pixbuf = get_pixbuf_by_path(path, size)

    if pixbuf:
        return pixbuf

    default_icon = get_default_icon_path(size)
    pixbuf = get_scaled_pixbuf_by_path(default_icon, size)

    if pixbuf:
        return pixbuf

    return get_unavailable_pixbuf(size)


@lru_cache(maxsize=128)
def get_cached_pixbuf_by_path(path, is_installed=True):
    """This keeps a global cache of pixbufs displayed in the uI;
    these can have the 'uninstalled' effect applied to them, and will
    be cached that way."""
    pixbuf = get_pixbuf_by_path(path)
    return pixbuf if is_installed else get_uninstalled_pixbuf(pixbuf)


def clear_pixbuf_caches():
    """This clears the pixbuf cached that get_cached_pixbuf_by_path() uses."""
    get_cached_pixbuf_by_path.cache_clear()


def get_default_icon_path(size):
    """Returns the path to the default icon for the size given; it's
    a Lutris icon for a square size, and a gradient for other sizes."""
    if not size or size[0] == size[1]:
        filename = "media/default_icon.png"
    else:
        filename = "media/default_banner.png"
    return os.path.join(datapath.get(), filename)


def get_pixbuf_by_path(path, size=None):
    """Reads an image file and returns the pixbuf. If you provide a size, this scales
    the file to fit that size, preserving the aspect ratio. If the file is missing or
    unreadable, this returns None."""
    if not system.path_exists(path, exclude_empty=True):
        return None

    try:
        if size:
            # new_from_file_at_size scales but preserves aspect ratio
            width, height = size
            return GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)

        return GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.GError:
        logger.error("Unable to load icon from image %s", path)


def get_scaled_pixbuf_by_path(path, size):
    """Reads an image file and returns the pixbuf. If you provide a size, this scales
    the file to full that size, ignore the aspect ratio. If the file is missing or
    unreadable, this returns None."""
    if not system.path_exists(path):
        return None

    try:
        if size:
            width, height = size
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width, height, preserve_aspect_ratio=False)

        return GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.GError:
        logger.error("Unable to load icon from image %s", path)


def get_uninstalled_pixbuf(original_pixbuf):
    """Applies a transparency effect to the pixbuf given, and returns a new pixbuf of
    the same size containing the result. If passed None, this returns None."""
    if not original_pixbuf:
        return None

    size = (original_pixbuf.get_width(), original_pixbuf.get_height())
    transparent_pixbuf = get_unavailable_pixbuf(size)
    original_pixbuf.composite(
        transparent_pixbuf,
        0,
        0,
        size[0],
        size[1],
        0,
        0,
        1,
        1,
        GdkPixbuf.InterpType.NEAREST,
        100,
    )
    return transparent_pixbuf


def get_unavailable_pixbuf(size):
    """Returns a partially transparent image in a pixbuf of the size given; we blend this into
    other images to indicate that a game is not installed."""
    width, height = size
    overlay_path = os.path.join(datapath.get(), "media/unavailable.png")
    return GdkPixbuf.Pixbuf.new_from_file_at_scale(overlay_path, width, height, preserve_aspect_ratio=False)


def has_stock_icon(name):
    """This tests if a GTK stock icon is known; if not we can try a fallback."""
    theme = Gtk.IconTheme.get_default()
    return theme.has_icon(name)


def get_stock_icon(name, size):
    """Return a pixbuf from a stock icon name"""
    theme = Gtk.IconTheme.get_default()
    try:
        return theme.load_icon(name, size, Gtk.IconLookupFlags.GENERIC_FALLBACK)
    except GLib.GError:
        logger.error("Failed to read icon %s", name)
        return None


def get_runtime_icon(icon_name, icon_format="image", size=None):
    """Return an icon based on the given name, format, size and type. Only
    the icons installed in Lutris's runtime directory are searched.

    Keyword arguments:
    icon_name -- The name of the icon to retrieve
    format -- The format of the icon, which should be either 'image' or 'pixbuf' (default 'image')
    size -- The size for the desired image (default None)
    """
    filename = icon_name.lower().replace(" ", "")
    # We prefer bitmaps over SVG, because we've got some SVG icons with the
    # wrong size (oops) and this avoids them.
    search_directories = [
        "icons/hicolor/64x64/apps",
        "icons/hicolor/24x24/apps",
        "icons",
        "icons/hicolor/scalable/apps",
        "icons/hicolor/symbolic/apps"]
    extensions = [".png", ".svg"]
    for search_dir in search_directories:
        for ext in extensions:
            icon_path = os.path.join(settings.RUNTIME_DIR, search_dir, filename + ext)
            if os.path.exists(icon_path):
                if icon_format == "image":
                    icon = Gtk.Image()
                    if size:
                        icon.set_from_pixbuf(get_pixbuf(icon_path, size))
                    else:
                        icon.set_from_file(icon_path)
                    return icon
                if icon_format == "pixbuf" and size:
                    return get_pixbuf(icon_path, size)
                raise ValueError("Invalid arguments")
    return None


def convert_to_background(background_path, target_size=(320, 1080)):
    """Converts a image to a pane background"""
    coverart = Image.open(background_path)
    coverart = coverart.convert("RGBA")

    target_width, target_height = target_size
    image_height = int(target_height * 0.80)  # 80% of the mask is visible
    orig_width, orig_height = coverart.size

    # Resize and crop coverart
    width = int(orig_width * (image_height / orig_height))
    offset = int((width - target_width) / 2)
    coverart = coverart.resize((width, image_height), resample=Image.BICUBIC)
    coverart = coverart.crop((offset, 0, target_width + offset, image_height))

    # Resize canvas of coverart by putting transparent pixels on the bottom
    coverart_bg = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
    coverart_bg.paste(coverart, (0, 0, target_width, image_height))

    # Apply a tint to the base image
    # tint = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 255))
    # coverart = Image.blend(coverart, tint, 0.6)

    # Paste coverart on transparent image while applying a gradient mask
    background = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
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
    base_image = base_image.resize((width, height), resample=Image.BICUBIC)
    base_image = base_image.crop((x_offset, y_offset, width - x_offset, height - y_offset))
    return base_image


def paste_overlay(base_image, overlay_image, position=0.7):
    base_width, base_height = base_image.size
    overlay_width, overlay_height = overlay_image.size
    offset_x = int((base_width - overlay_width) / 2)
    offset_y = int((base_height - overlay_height) / 2)
    base_image.paste(
        overlay_image, (
            offset_x,
            offset_y,
            overlay_width + offset_x,
            overlay_height + offset_y
        ),
        mask=overlay_image
    )
    return base_image


def image2pixbuf(image):
    """Converts a PIL Image to a GDK Pixbuf"""
    image_array = array.array('B', image.tobytes())
    width, height = image.size
    return GdkPixbuf.Pixbuf.new_from_data(image_array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4)


def get_link_button(text):
    """Return a transparent text button for the side panels"""
    button = Gtk.Button(text, visible=True)
    button.props.relief = Gtk.ReliefStyle.NONE
    button.get_children()[0].set_alignment(0, 0.5)
    button.get_style_context().add_class("panel-button")
    button.set_size_request(-1, 24)
    return button


def load_icon_theme():
    """Add the lutris icon folder to the default theme"""
    icon_theme = Gtk.IconTheme.get_default()
    local_theme_path = os.path.join(settings.RUNTIME_DIR, "icons")
    if local_theme_path not in icon_theme.get_search_path():
        icon_theme.prepend_search_path(local_theme_path)
