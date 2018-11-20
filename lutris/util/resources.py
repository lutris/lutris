"""Utility module to handle media resources"""
import shutil
import os
import concurrent.futures
from urllib.parse import urlparse, parse_qsl
from gi.repository import GLib

from lutris import api, settings
from lutris.util.http import Request
from lutris.util.log import logger

from lutris.util import system

BANNER = "banner"
ICON = "icon"


def get_icon_path(game, icon_type):
    """Return the absolute path for a game icon/banner"""
    if icon_type == BANNER:
        return os.path.join(settings.BANNER_PATH, "%s.jpg" % game)
    elif icon_type == ICON:
        return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game)
    return None


def has_icon(game, icon_type):
    """Return True if the game has the icon of `icon_type`"""
    if icon_type == BANNER:
        icon_path = get_icon_path(game, BANNER)
        return system.path_exists(icon_path)
    elif icon_type == ICON:
        icon_path = get_icon_path(game, ICON)
        return system.path_exists(icon_path)
    return False


def fetch_icons(game_slugs, callback=None):
    """Get missing icons from lutris.net"""
    no_banners = [slug for slug in game_slugs if not has_icon(slug, BANNER)]
    no_icons = [slug for slug in game_slugs if not has_icon(slug, ICON)]

    # Remove duplicate slugs
    missing_media_slugs = list(set(no_banners) | set(no_icons))
    if not missing_media_slugs:
        logger.debug("No icon are missing")
        return
    logger.debug(
        "Requesting missing icons from API for %d games", len(missing_media_slugs)
    )
    results = api.get_games(game_slugs=missing_media_slugs)
    if not results:
        logger.warning("Unable to get games, check your network connectivity")

    new_icon = False
    banner_downloads = []
    icon_downloads = []
    updated_slugs = []
    for game in results:
        if game["slug"] in no_banners:
            banner_url = game["banner_url"]
            if banner_url:
                dest_path = get_icon_path(game["slug"], BANNER)
                banner_downloads.append((game["banner_url"], dest_path))
                updated_slugs.append(game["slug"])
        if game["slug"] in no_icons:
            icon_url = game["icon_url"]
            if icon_url:
                dest_path = get_icon_path(game["slug"], ICON)
                icon_downloads.append((game["icon_url"], dest_path))
                updated_slugs.append(game["slug"])
                new_icon = True

    updated_slugs = list(set(updated_slugs))  # Deduplicate slugs
    downloads = banner_downloads + icon_downloads
    if downloads:
        logger.debug("Downloading %d files", len(downloads))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futs = [
            executor.submit(download_media, url, dest_path)
            for url, dest_path in downloads
        ]
        concurrent.futures.wait(futs)

    if new_icon:
        udpate_desktop_icons()

    if updated_slugs and callback:
        callback(updated_slugs)


def udpate_desktop_icons():
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
    logger.debug("Downloading %s to %s", url, dest)
    if system.path_exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            return
    request = Request(url).get()
    request.write_to_file(dest)


def parse_installer_url(url):
    """
    Parses `lutris:` urls, extracting any info necessary to install or run a game.
    """
    action = None
    try:
        parsed_url = urlparse(url, scheme="lutris")
    except Exception:  # pylint: disable=broad-except
        logger.warning("Unable to parse url %s", url)
        return False
    if parsed_url.scheme != "lutris":
        return False
    url_path = parsed_url.path
    if not url_path:
        return False
    # urlparse can't parse if the path only contain numbers
    # workaround to remove the scheme manually:
    if url_path.startswith("lutris:"):
        url_path = url_path[7:]

    url_parts = url_path.split("/")
    if len(url_parts) == 2:
        action = url_parts[0]
        game_slug = url_parts[1]
    elif len(url_parts) == 1:
        game_slug = url_parts[0]
    else:
        raise ValueError("Invalid lutris url %s" % url)

    revision = None
    if parsed_url.query:
        query = dict(parse_qsl(parsed_url.query))
        revision = query.get("revision")
    return {"game_slug": game_slug, "revision": revision, "action": action}
