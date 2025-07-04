import json
import os
import random
import time
from typing import Any, Dict, List, Optional

from lutris.database.services import ServiceGameCollection
from lutris.util import system
from lutris.util.http import HTTPError, download_file
from lutris.util.log import logger
from lutris.util.portals import TrashPortal


def resolve_media_path(possible_paths: List[str]) -> str:
    """Selects the best path from a list of paths to media. This will take the first
    one that exists and has contents, or the just first one if none are usable."""
    if len(possible_paths) > 1:
        for path in possible_paths:
            if system.path_exists(path, exclude_empty=True) and os.path.isfile(path):
                return path
    elif not possible_paths:
        raise ValueError("resolve_media_path() requires at least one path.")

    return possible_paths[0]


class ServiceMedia:
    """Information about the service's media format"""

    service = NotImplemented
    size = NotImplemented
    source = "remote"  # set to local if the files don't need to be downloaded
    visible = True  # This media should be displayed as an option in the UI
    dest_path = NotImplemented
    file_patterns = NotImplemented
    api_field = NotImplemented
    url_pattern = "%s"

    def __init__(self):
        if self.dest_path and not system.path_exists(self.dest_path):
            os.makedirs(self.dest_path)

    def get_filename(self, slug):
        return self.file_patterns[0] % slug

    def get_possible_media_paths(self, slug: str) -> List[str]:
        """Returns a list of each path where the media might be found. At most one of these should
        be found, but they are in a priority order - the first is in the preferred format."""
        return [os.path.join(self.dest_path, pattern % slug) for pattern in self.file_patterns]

    def trash_media(
        self,
        slug: str,
        completion_function: Optional[TrashPortal.CompletionFunction] = None,
        error_function: Optional[TrashPortal.ErrorFunction] = None,
    ) -> None:
        """Sends each media file for a game to the trash, and invokes callsbacks when this
        has been completed or has failed."""
        paths = [path for path in self.get_possible_media_paths(slug) if os.path.exists(path)]
        if paths:
            TrashPortal(paths, completion_function=completion_function, error_function=error_function)
        elif completion_function:
            completion_function()

    def get_media_url(self, details: Dict[str, Any]) -> Optional[str]:
        if self.api_field not in details:
            logger.warning("No field '%s' in API game %s", self.api_field, details)
            return None
        if not details[self.api_field]:
            return None
        return self.url_pattern % details[self.api_field]

    def get_media_urls(self) -> Dict[str, str]:
        """Return URLs for icons and logos from a service"""
        if self.source == "local":
            return {}
        service_games = ServiceGameCollection.get_for_service(self.service)
        medias: Dict[str, str] = {}
        for game in service_games:
            if not game["details"]:
                continue
            details = json.loads(game["details"])
            media_url = self.get_media_url(details)
            if not media_url:
                continue
            medias[game["slug"]] = media_url
        return medias

    def download(self, slug, url):
        """Downloads the banner if not present"""
        if not url:
            return
        cache_path = os.path.join(self.dest_path, self.get_filename(slug))
        if system.path_exists(cache_path, exclude_empty=True):
            return
        if system.path_exists(cache_path):
            cache_stats = os.stat(cache_path)
            # Empty files have a life time between 1 and 2 weeks, retry them after
            if time.time() - cache_stats.st_mtime < 3600 * 24 * random.choice(range(7, 15)):
                return cache_path
            os.unlink(cache_path)
        try:
            return download_file(url, cache_path, raise_errors=True)
        except HTTPError as ex:
            logger.error("Failed to download %s: %s", url, ex)

    @property
    def custom_media_storage_size(self):
        """The size this media is stored in when customized; we accept
        whatever we get when we download the media, however."""
        return self.size

    @property
    def config_ui_size(self):
        """The size this media should be shown at when in the configuration UI."""
        return self.size

    def run_system_update_desktop_icons(self):
        """Update the desktop, if this media type appears there. Most don't."""

    def render(self):
        """Used if the media requires extra processing"""
