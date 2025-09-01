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


class MediaPath:
    """An object to describe a media file along with the media size- which
    is defined by Lutris, not the size of the image in the file. Note that
    the file may not exist."""

    def __init__(self, path: str, service_media: "ServiceMedia"):
        self.path = path
        self.service_media = service_media

    @property
    def width(self) -> int:
        return self.service_media.size[0]

    @property
    def height(self) -> int:
        return self.service_media.size[1]

    @property
    def exists(self) -> bool:
        return system.path_exists(self.path, exclude_empty=True) and os.path.isfile(self.path)

    def __repr__(self) -> str:
        return self.path


def resolve_media_path(possible_paths: List[MediaPath]) -> MediaPath:
    """Selects the best path from a list of paths to media. This will take the first
    one that exists and has contents, or the just first one if none are usable."""
    if len(possible_paths) > 1:
        for mp in possible_paths:
            if mp.exists:
                return mp
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

    def get_possible_media_paths(self, slug: str) -> List[MediaPath]:
        """Returns a list of each path where the media might be found. At most one of these should
        be found, but they are in a priority order - the first is in the preferred format."""
        return [MediaPath(os.path.join(self.dest_path, pattern % slug), self) for pattern in self.file_patterns]

    def get_fallback_media_paths(self, slug, service):
        """Returns a list of each path where media can be found, but including paths from other
        media objects selected by this one. Again, the first is the preferred path."""
        medias = [self]
        medias.extend(mt() for mt in service.medias.values())

        def similarity(media):
            diff = abs(media.size[1] - self.size[1])
            return diff if media.size[1] >= self.size[1] else diff + 1000

        seen = set()

        def visit(path):
            if path in seen:
                return False
            seen.add(path)
            return True

        ordered = sorted(medias, key=similarity)
        return [path for media in ordered for path in media.get_possible_media_paths(slug) if visit(path.path)]

    def trash_media(
        self,
        slug: str,
        completion_function: Optional[TrashPortal.CompletionFunction] = None,
        error_function: Optional[TrashPortal.ErrorFunction] = None,
    ) -> None:
        """Sends each media file for a game to the trash, and invokes callsbacks when this
        has been completed or has failed."""
        paths = [mp.path for mp in self.get_possible_media_paths(slug) if os.path.exists(mp.path)]
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
