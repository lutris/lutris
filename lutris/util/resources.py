"""Utility module to handle media resources"""
# Standard Library
import os

# Third Party Libraries
from gi.repository import GLib

# Lutris Modules
from lutris import settings
from lutris.util import system
from lutris.util.http import HTTPError, Request


def get_icon_path(game_slug, icon_type="icon"):
    """Return the absolute path for a game_slug icon"""
    if icon_type.startswith("banner"):
        return os.path.join(settings.BANNER_PATH, "%s.jpg" % game_slug)
    if icon_type.startswith("icon"):
        return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game_slug)
    raise ValueError("Invalid icon type %s" % icon_type)


def get_banner_path(game_slug):
    """Return the absolute path for a game_slug banner"""
    return get_icon_path(game_slug, "banner")


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
