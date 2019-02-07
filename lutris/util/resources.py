"""Utility module to handle media resources"""
import os
import concurrent.futures
from gi.repository import GLib

from lutris import settings
from lutris.util.http import Request
from lutris.util.log import logger

from lutris.util import system

BANNER = "banner"
ICON = "icon"


def get_icon_path(game_slug, icon_type=ICON):
    """Return the absolute path for a game_slug icon/banner"""
    if icon_type == BANNER:
        return os.path.join(settings.BANNER_PATH, "%s.jpg" % game_slug)
    if icon_type == ICON:
        return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game_slug)
    raise ValueError("Invalid icon type %s" % icon_type)


def get_banner_path(game_slug):
    return get_icon_path(game_slug, BANNER)


def fetch_icons(lutris_media, callback):
    """Download missing icons from lutris.net"""
    if not lutris_media:
        return

    available_banners, available_icons = lutris_media
    downloads = [
        (slug, available_banners[slug], get_icon_path(slug, BANNER))
        for slug in available_banners
    ] + [
        (slug, available_icons[slug], get_icon_path(slug, ICON))
        for slug in available_icons
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        future_downloads = {
            executor.submit(download_media, url, dest_path): slug
            for slug, url, dest_path in downloads
        }
        for future in concurrent.futures.as_completed(future_downloads):
            slug = future_downloads[future]
            try:
                future.result()
            except Exception as ex:  # pylint: disable=broad-except
                logger.exception('%r generated an exception: %s', slug, ex)
            else:
                GLib.idle_add(callback, slug, priority=GLib.PRIORITY_LOW)

    if bool(available_icons):
        update_desktop_icons()


def update_desktop_icons():
    """Update Icon for GTK+ desktop manager"""
    gtk_update_icon_cache = system.find_executable("gtk-update-icon-cache")
    if gtk_update_icon_cache:
        os.system(
            "gtk-update-icon-cache -tf %s"
            % os.path.join(GLib.get_user_data_dir(), "icons", "hicolor")
        )

    # Other desktop manager cache command must be added here when needed


def download_media(url, dest, overwrite=False):
    """Save a remote media locally"""
    if system.path_exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            return dest
    request = Request(url).get()
    request.write_to_file(dest)
    return dest
