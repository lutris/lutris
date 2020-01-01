"""Various utilities using the GObject framework"""
import os
import array
try:
    from PIL import Image
except ImportError:
    Image = None
from gi.repository import GdkPixbuf, GLib, Gtk, Gio, Gdk

from lutris.util.log import logger
from lutris.util import datapath
from lutris.util import system
from lutris.util import resources
from lutris import settings


BANNER_SIZE = (184, 69)
BANNER_SMALL_SIZE = (120, 45)
ICON_SIZE = (32, 32)
ICON_SMALL_SIZE = (20, 20)


IMAGE_SIZES = {
    "icon_small": ICON_SMALL_SIZE,
    "icon": ICON_SIZE,
    "banner_small": BANNER_SMALL_SIZE,
    "banner": BANNER_SIZE,
}


def get_main_window(widget):
    """Return the application's main window from one of its widget"""
    parent = widget.get_toplevel()
    if not isinstance(parent, Gtk.Window):
        # The sync dialog may have closed
        parent = Gio.Application.get_default().props.active_window
    for window in parent.application.get_windows():
        if "LutrisWindow" in window.__class__.__name__:
            return window


def open_uri(uri):
    """Opens a local or remote URI with the default application"""
    system.reset_library_preloads()
    try:
        Gtk.show_uri(None, uri, Gdk.CURRENT_TIME)
    except GLib.Error as ex:
        logger.exception("Failed to open URI %s: %s, falling back to xdg-open", uri, ex)
        system.execute(["xdg-open", uri])


def get_pixbuf(image, size, fallback=None):
    """Return a pixbuf from file `image` at `size` or fallback to `fallback`"""
    width, heigth = size
    if system.path_exists(image):
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_size(image, width, heigth)
        except GLib.GError:
            logger.error("Unable to load icon from image %s", image)
    if system.path_exists(fallback):
        return GdkPixbuf.Pixbuf.new_from_file_at_size(fallback, width, heigth)
    if image and not image.startswith("/"):
        return get_stock_icon(image, width)
    return None


def get_stock_icon(name, size):
    """Return a picxbuf from a stock icon name"""
    theme = Gtk.IconTheme.get_default()
    try:
        return theme.load_icon(name, size, Gtk.IconLookupFlags.GENERIC_FALLBACK)
    except GLib.GError:
        logger.error("Failed to read icon %s", name)
        return None


def get_icon(icon_name, format="image", size=None, icon_type="runner"):
    """Return an icon based on the given name, format, size and type.

    Keyword arguments:
    icon_name -- The name of the icon to retrieve
    format -- The format of the icon, which should be either 'image' or 'pixbuf' (default 'image')
    size -- The size for the desired image (default None)
    icon_type -- Retrieve either a 'runner' or 'platform' icon (default 'runner')
    """
    filename = icon_name.lower().replace(" ", "") + ".png"
    icon_path = os.path.join(datapath.get(), "media/" + icon_type + "_icons", filename)
    if not os.path.exists(icon_path):
        logger.error("Unable to find icon '%s'", icon_path)
        return None
    if format == "image":
        icon = Gtk.Image()
        if size:
            icon.set_from_pixbuf(get_pixbuf(icon_path, size))
        else:
            icon.set_from_file(icon_path)
        return icon
    elif format == "pixbuf" and size:
        return get_pixbuf(icon_path, size)
    raise ValueError("Invalid arguments")


def get_overlay(overlay_path, size):
    width, height = size
    transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
        overlay_path, width, height
    )
    transparent_pixbuf = transparent_pixbuf.scale_simple(
        width, height, GdkPixbuf.InterpType.NEAREST
    )
    return transparent_pixbuf


def get_pixbuf_for_game(game_slug, icon_type, is_installed=True):
    if icon_type.startswith("banner"):
        default_icon_path = os.path.join(datapath.get(), "media/default_banner.png")
        icon_path = resources.get_banner_path(game_slug)
    elif icon_type.startswith("icon"):
        default_icon_path = os.path.join(datapath.get(), "media/default_icon.png")
        icon_path = resources.get_icon_path(game_slug)
    else:
        logger.error("Invalid icon type '%s'", icon_type)
        return None

    size = IMAGE_SIZES[icon_type]

    pixbuf = get_pixbuf(icon_path, size, fallback=default_icon_path)
    if not is_installed:
        unavailable_game_overlay = os.path.join(datapath.get(), "media/unavailable.png")
        transparent_pixbuf = get_overlay(unavailable_game_overlay, size).copy()
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
    return pixbuf


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
    return GdkPixbuf.Pixbuf.new_from_data(
        image_array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4
    )


def get_pixbuf_for_panel(game_slug):
    """Return the pixbuf for the game panel background"""
    if Image is None:
        # PIL is not available
        return
    source_path = os.path.join(settings.COVERART_PATH, "%s.jpg" % game_slug)
    if not os.path.exists(source_path):
        source_path = os.path.join(datapath.get(), "media/generic-panel-bg.png")
    dest_path = os.path.join(settings.CACHE_DIR, "panel_bg.png")
    background = convert_to_background(source_path)
    background.save(dest_path)
    return dest_path


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
