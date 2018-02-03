import os
import re
import concurrent.futures
from urllib.parse import urlparse, parse_qsl

from lutris import settings
from lutris import api
from lutris.util.log import logger
from lutris.util.http import Request

BANNER = "banner"
ICON = "icon"


def get_icon_path(game, icon_type):
    if icon_type == BANNER:
        return os.path.join(settings.BANNER_PATH, "%s.jpg" % game)
    if icon_type == ICON:
        return os.path.join(settings.ICON_PATH, "lutris_%s.png" % game)


def has_icon(game, icon_type):
    if icon_type == BANNER:
        icon_path = get_icon_path(game, BANNER)
        return os.path.exists(icon_path)
    elif icon_type == ICON:
        icon_path = get_icon_path(game, ICON)
        return os.path.exists(icon_path)


def fetch_icons(game_slugs, callback=None):
    no_banners = [slug for slug in game_slugs if not has_icon(slug, BANNER)]
    no_icons = [slug for slug in game_slugs if not has_icon(slug, ICON)]

    # Remove duplicate slugs
    missing_media_slugs = list(set(no_banners) | set(no_icons))
    if not missing_media_slugs:
        return

    results = api.get_games(game_slugs=missing_media_slugs)

    new_icon = False
    banner_downloads = []
    icon_downloads = []
    updated_slugs = []
    for game in results:
        if game['slug'] in no_banners:
            banner_url = game['banner_url']
            if banner_url:
                dest_path = get_icon_path(game['slug'], BANNER)
                banner_downloads.append((game['banner_url'], dest_path))
                updated_slugs.append(game['slug'])
        if game['slug'] in no_icons:
            icon_url = game['icon_url']
            if icon_url:
                dest_path = get_icon_path(game['slug'], ICON)
                icon_downloads.append((game['icon_url'], dest_path))
                updated_slugs.append(game['slug'])
                new_icon = True

    updated_slugs = list(set(updated_slugs))  # Deduplicate slugs

    downloads = banner_downloads + icon_downloads
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futs = [executor.submit(download_media, url, dest_path)
                for url, dest_path in downloads]
        concurrent.futures.wait(futs)

    if (new_icon):
        udpate_desktop_icons()

    if updated_slugs and callback:
        callback(updated_slugs)

def udpate_desktop_icons():
    os.system("xdg-icon-resource forceupdate")

def download_media(url, dest, overwrite=False):
    if os.path.exists(dest):
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
    except:
        return False
    if parsed_url.scheme != "lutris":
        return False
    url_path = parsed_url.path
    if not url_path:
        return False
    # urlparse can't parse if the path only contain numbers
    # workaround to remove the scheme manually:
    if url_path.startswith('lutris:'):
        url_path = url_path[7:]

    url_parts = url_path.split('/')
    if len(url_parts) == 2:
        action = url_parts[0]
        game_slug = url_parts[1]
    elif len(url_parts) == 1:
        game_slug = url_parts[0]
    else:
        raise ValueError('Invalid lutris url %s' % url)

    revision = None
    if parsed_url.query:
        query = dict(parse_qsl(parsed_url.query))
        revision = query.get('revision')
    return {
        'game_slug': game_slug,
        'revision': revision,
        'action': action
    }
