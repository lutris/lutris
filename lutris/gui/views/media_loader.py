"""Loads game media in parallel"""
import concurrent.futures
from typing import Dict

from gi.repository import GObject

from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.log import logger


class MediaLoader(GObject.Object):
    __gsignals__ = {
        "icon-loaded": (GObject.SIGNAL_RUN_FIRST, None, (str, str)),
    }

    num_workers = 3

    def download_icons(self, media_urls: Dict[str, str], service_media: ServiceMedia):
        """Download a list of media files concurrently.

        Limits the number of simultaneous downloads to avoid API throttling
        and UI being overloaded with signals.
        """

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
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
                if system.path_exists(path):
                    self.emit("icon-loaded", slug, path)
