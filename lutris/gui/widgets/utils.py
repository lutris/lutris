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
    'banner': BANNER_SIZE,
    'banner_small': BANNER_SMALL_SIZE,
    'icon': ICON_SIZE,
    'icon_small': ICON_SMALL_SIZE
}


def get_pixbuf(image, default_image, size):
    """Return a pixbuf from file `image` at `size` or fallback to `default_image`"""
    x, y = size
    if not os.path.exists(image):
        image = default_image
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(image, x, y)
    except GLib.GError:
        if default_image:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(default_image, x, y)
        else:
            raise
    return pixbuf


def get_runner_icon(runner_name, format='image', size=None):
    icon_path = os.path.join(datapath.get(), 'media/runner_icons',
                             runner_name + '.png')
    if not os.path.exists(icon_path):
        logger.error("Unable to find icon '%s'", icon_path)
        return
    if format == 'image':
        icon = Gtk.Image()
        icon.set_from_file(icon_path)
    elif format == 'pixbuf' and size:
        icon = get_pixbuf(icon_path, None, size)
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
    if icon_type in ("banner", "banner_small"):
        default_icon_path = DEFAULT_BANNER
        icon_path = datapath.get_banner_path(game_slug)
    elif icon_type in ("icon", "icon_small"):
        default_icon_path = DEFAULT_ICON
        icon_path = datapath.get_icon_path(game_slug)
    else:
        logger.error("Invalid icon type '%s'", icon_type)
        return

    size = IMAGE_SIZES[icon_type]

    pixbuf = get_pixbuf(icon_path, default_icon_path, size)
    if not is_installed:
        transparent_pixbuf = get_overlay(size).copy()
        pixbuf.composite(transparent_pixbuf, 0, 0, size[0], size[1],
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf


