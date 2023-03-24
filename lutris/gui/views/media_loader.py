"""Loads game media in parallel"""
import concurrent.futures

from lutris.gui.widgets.utils import invalidate_media_caches
from lutris.util import system
from lutris.util.log import logger


def download_media(media_urls, service_media):
    """Download a list of media files concurrently.

    Limits the number of simultaneous downloads to avoid API throttling
    and UI being overloaded with signals.
    """
    icons = {}
    num_workers = 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_downloads = {
            executor.submit(service_media.download, slug, url): slug
            for slug, url in media_urls.items()
            if url
        }
        for future in concurrent.futures.as_completed(future_downloads):
            slug = future_downloads[future]
            try:
                path = future.result()
            except Exception as ex:  # pylint: disable=broad-except
                logger.exception('%r failed: %s', slug, ex)
                path = None
            if system.path_exists(path):
                icons[slug] = path

    invalidate_media_caches()
    return icons
