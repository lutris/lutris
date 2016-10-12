import os
import re
import concurrent.futures

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

    response = api.get_games(game_slugs=missing_media_slugs)
    if not response:
        logger.warning('Unable to get games from API')
        return
    results = response['results']
    while response['next']:
        page_match = re.search(r'page=(\d+)', response['next'])
        if page_match:
            page = page_match.group(1)
        else:
            logger.error("No page found in %s", response['next'])
            break
        response = api.get_games(game_slugs=missing_media_slugs, page=page)
        results += response['results']

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

    updated_slugs = list(set(updated_slugs))  # Deduplicate slugs

    downloads = banner_downloads + icon_downloads
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for url, dest_path in downloads:
            executor.submit(download_media, url, dest_path)

    if updated_slugs and callback:
        callback(updated_slugs)


def download_media(url, dest, overwrite=False):
    if os.path.exists(dest):
        if overwrite:
            os.remove(dest)
        else:
            return
    request = Request(url).get()
    request.write_to_file(dest)
