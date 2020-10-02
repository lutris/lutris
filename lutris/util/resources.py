"""Utility module to handle media resources"""
import os

from gi.repository import GLib

from lutris import settings
from lutris.util import system
from lutris.util.http import HTTPError, Request
from lutris.util.image_type import ImageType


def get_image_path(game_slug, image_type=ImageType.icon):
    """Return the absolute path for a game_slug icon"""
    if image_type & ImageType.banner:
        return os.path.join(settings.BANNER_PATH, "%s.jpg" % game_slug)
    if image_type & ImageType.icon:
        return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game_slug)
    raise ValueError("Invalid image type %s" % image_type)


def get_banner_path(game_slug):
    """Return the absolute path for a game_slug banner"""
    return get_image_path(game_slug, ImageType.banner)


def get_icon_path(game_slug):
    """Return the absolute path for a game_slug banner"""
    return get_image_path(game_slug, ImageType.icon)


def update_desktop_icons():
    """Update Icon for GTK+ desktop manager
    Other desktop manager icon cache commands must be added here if needed
    """
    gtk_update_icon_cache = system.find_executable("gtk-update-icon-cache")
    if gtk_update_icon_cache:
        os.system("gtk-update-icon-cache -tf %s" % os.path.join(GLib.get_user_data_dir(), "icons", "hicolor"))


def download_media(url, dest, overwrite=False):
    """Save a remote media locally"""
    if system.path_exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            return dest
    try:
        request = Request(url).get()
    except HTTPError:
        return
    request.write_to_file(dest)
    return dest
