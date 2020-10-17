"""Various utilities using the GObject framework"""
import array
import os

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from lutris import settings
from lutris.util import datapath, system
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
    system.reset_library_preloads()
    try:
        Gtk.show_uri(None, uri, Gdk.CURRENT_TIME)
    except GLib.Error as ex:
        logger.exception("Failed to open URI %s: %s, falling back to xdg-open", uri, ex)
        system.execute(["xdg-open", uri])


def get_pixbuf(image, size, fallback=None, is_installed=True):
    """Return a pixbuf from file `image` at `size` or fallback to `fallback`"""
    width, height = size
    pixbuf = None

    if system.path_exists(image):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(image, width, height)
            pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.NEAREST)
        except GLib.GError:
            logger.error("Unable to load icon from image %s", image)
    if system.path_exists(fallback):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(fallback, width, height)
    if not pixbuf:
        return None
    if is_installed:
        return pixbuf
    overlay = os.path.join(datapath.get(), "media/unavailable.png")
    transparent_pixbuf = get_overlay(overlay, size).copy()
    pixbuf.composite(
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


def get_stock_icon(name, size):
    """Return a pixbuf from a stock icon name"""
    theme = Gtk.IconTheme.get_default()
    try:
        return theme.load_icon(name, size, Gtk.IconLookupFlags.GENERIC_FALLBACK)
    except GLib.GError:
        logger.error("Failed to read icon %s", name)
        return None


def get_icon(icon_name, icon_format="image", size=None, icon_type="runner"):
    """Return an icon based on the given name, format, size and type.

    Keyword arguments:
    icon_name -- The name of the icon to retrieve
    format -- The format of the icon, which should be either 'image' or 'pixbuf' (default 'image')
    size -- The size for the desired image (default None)
    icon_type -- Retrieve either a 'runner' or 'platform' icon (default 'runner')
    """
    filename = icon_name.lower().replace(" ", "") + ".png"
    icon_path = os.path.join(settings.RUNTIME_DIR, "icons/hicolor/64x64/apps", filename)
    if not os.path.exists(icon_path):
        logger.error("Unable to find icon '%s'", icon_path)
        return None
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


def get_overlay(overlay_path, size):
    width, height = size
    transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(overlay_path, width, height)
    transparent_pixbuf = transparent_pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.NEAREST)
    return transparent_pixbuf


def get_default_icon(size):
    if size[0] == size[1]:
        return os.path.join(datapath.get(), "media/default_icon.png")
    return os.path.join(datapath.get(), "media/default_banner.png")


def get_pixbuf_for_game(image_abspath, size, is_installed=True):
    return get_pixbuf(image_abspath, size, fallback=get_default_icon(size), is_installed=is_installed)


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


def image2pixbuf(image):
    """Converts a PIL Image to a GDK Pixbuf"""
    image_array = array.array('B', image.tobytes())
    width, height = image.size
    return GdkPixbuf.Pixbuf.new_from_data(image_array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4)


def get_builder_from_file(glade_file):
    ui_filename = os.path.join(datapath.get(), "ui", glade_file)
    if not os.path.exists(ui_filename):
        raise ValueError("ui file does not exists: %s" % ui_filename)

    builder = Gtk.Builder()
    builder.add_from_file(ui_filename)
    return builder


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
