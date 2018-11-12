import os
from gi.repository import GdkPixbuf, GLib, Gtk

from lutris.util.log import logger
from lutris.util import datapath


UNAVAILABLE_GAME_OVERLAY = os.path.join(datapath.get(),
                                        'media/unavailable.png')

BANNER_SIZE = (184, 69)
BANNER_SMALL_SIZE = (120, 45)
ICON_SIZE = (32, 32)
ICON_SMALL_SIZE = (20, 20)

DEFAULT_BANNER = os.path.join(datapath.get(), 'media/default_banner.png')
DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')

IMAGE_SIZES = {
    'icon_small': ICON_SMALL_SIZE,
    'icon': ICON_SIZE,
    'banner_small': BANNER_SMALL_SIZE,
    'banner': BANNER_SIZE
}


def get_pixbuf(image, size, fallback=None):
    """Return a pixbuf from file `image` at `size` or fallback to `fallback`"""
    x, y = size
    if not os.path.exists(image):
        image = fallback
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(image, x, y)
    except GLib.GError:
        if fallback:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(fallback, x, y)
        else:
            raise
    return pixbuf


def get_icon(icon_name, format='image', size=None, icon_type='runner'):
    """Return an icon based on the given name, format, size and type.

    Keyword arguments:
    icon_name -- The name of the icon to retrieve
    format -- The format of the icon, which should be either 'image' or 'pixbuf' (default 'image')
    size -- The size for the desired image (default None)
    icon_type -- Retrieve either a 'runner' or 'platform' icon (default 'runner')
    """
    filename = icon_name.lower().replace(' ', '') + '.png'
    icon_path = os.path.join(datapath.get(), 'media/' + icon_type + '_icons', filename)
    if not os.path.exists(icon_path):
        logger.error("Unable to find icon '%s'", icon_path)
        return None
    if format == 'image':
        icon = Gtk.Image()
        icon.set_from_file(icon_path)
    elif format == 'pixbuf' and size:
        icon = get_pixbuf(icon_path, size)
    else:
        raise ValueError("Invalid arguments")
    return icon


def get_overlay(size):
    x, y = size
    transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
        UNAVAILABLE_GAME_OVERLAY, x, y
    )
    transparent_pixbuf = transparent_pixbuf.scale_simple(
        x, y, GdkPixbuf.InterpType.NEAREST
    )
    return transparent_pixbuf


def get_pixbuf_for_game(game_slug, icon_type, is_installed=True):
    if icon_type.startswith("banner"):
        default_icon_path = DEFAULT_BANNER
        icon_path = datapath.get_banner_path(game_slug)
    elif icon_type.startswith("icon"):
        default_icon_path = DEFAULT_ICON
        icon_path = datapath.get_icon_path(game_slug)
    else:
        logger.error("Invalid icon type '%s'", icon_type)
        return None

    size = IMAGE_SIZES[icon_type]

    pixbuf = get_pixbuf(icon_path, size, fallback=default_icon_path)
    if not is_installed:
        transparent_pixbuf = get_overlay(size).copy()
        pixbuf.composite(transparent_pixbuf, 0, 0, size[0], size[1],
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf
