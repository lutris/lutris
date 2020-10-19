"""Loads game media in parallel"""
import concurrent.futures

from gi.repository import GObject

from lutris.util.log import logger


class MediaLoader(GObject.Object):
    __gsignals__ = {
        "icon-loaded": (GObject.SIGNAL_RUN_FIRST, None, (str, str, int, int)),
    }

    num_workers = 3

    def download_icons(self, media_urls, service_media):
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
                else:
                    if path:
                        self.emit("icon-loaded", slug, path, service_media.size[0], service_media.size[1])
