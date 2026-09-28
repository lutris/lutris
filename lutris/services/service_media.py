import json
import os
import random
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from lutris.database.services import ServiceGameCollection
from lutris.gui.widgets.utils import Image, is_transparent_logo, paste_overlay, scale_to_fit, thumbnail_image
from lutris.util import system
from lutris.util.http import HTTPError, download_file
from lutris.util.log import logger
from lutris.util.portals import TrashPortal

if TYPE_CHECKING:
    from lutris.services.base import BaseService


class MediaPath:
    """An object to describe a media file along with the media size- which
    is defined by Lutris, not the size of the image in the file. Note that
    the file may not exist."""

    def __init__(self, path: str, service_media: "ServiceMedia", size: tuple[int, int] | None = None):
        self.path = path
        self.service_media = service_media
        self.size = size or service_media.size

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    @property
    def exists(self) -> bool:
        return system.path_exists(self.path, exclude_empty=True) and os.path.isfile(self.path)

    def scale_to_fit(self, max_size: tuple[int, int]) -> "MediaPath":
        if max_size != self.size:
            x_factor = max_size[0] / self.width
            y_factor = max_size[1] / self.height
            factor = min(x_factor, y_factor)
            scaled_width = int(self.width * factor)
            scaled_height = int(self.height * factor)
            return MediaPath(self.path, self.service_media, (scaled_width, scaled_height))
        return self

    def __repr__(self) -> str:
        return self.path


def resolve_media_path(possible_paths: list[MediaPath]) -> MediaPath:
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
    can_be_fallback = True

    def __init__(self):
        if self.dest_path and not system.path_exists(self.dest_path):
            os.makedirs(self.dest_path)

    def get_filename(self, slug):
        return self.file_patterns[0] % slug

    def get_possible_media_paths(self, slug: str) -> list[MediaPath]:
        """Returns a list of each path where the media might be found. At most one of these should
        be found, but they are in a priority order - the first is in the preferred format."""
        return [MediaPath(os.path.join(self.dest_path, pattern % slug), self) for pattern in self.file_patterns]

    def get_fallback_media_path(self, services: Iterable[tuple["BaseService", Callable[[], str]]]) -> MediaPath | None:
        """Returns the media path to use when none of the possible paths (above) actually exist.
        This may be scaled down so it no taller than this media's height.

        This method finds the media that is nearest to the size of this media, and
        then evaluates the provided callables to obtain slugs, starting with the nearest
        match. As soon as it finds a media that exists, it will return it. If it finds
        none, it returns None.
        """

        medias = [(mt(), t[1]) for t in services for mt in t[0].medias.values()]

        def similarity(media: tuple[ServiceMedia, Callable[[], str]]) -> int:
            diff = abs(media[0].size[1] - self.size[1])
            return diff if media[0].size[1] >= self.size[1] else diff + 1000

        for media, slug_function in sorted(medias, key=similarity):
            if media.can_be_fallback:
                slug = slug_function()
                if slug:
                    for mp in media.get_possible_media_paths(slug):
                        if mp.exists:
                            return mp.scale_to_fit(self.size)

        return None

    def trash_media(
        self,
        slug: str,
        completion_function: TrashPortal.CompletionFunction | None = None,
        error_function: TrashPortal.ErrorFunction | None = None,
    ) -> None:
        """Sends each media file for a game to the trash, and invokes callsbacks when this
        has been completed or has failed."""
        paths = [mp.path for mp in self.get_possible_media_paths(slug) if os.path.exists(mp.path)]
        if paths:
            TrashPortal(paths, completion_function=completion_function, error_function=error_function)
        elif completion_function:
            completion_function()

    def get_media_url(self, details: dict[str, Any]) -> str | None:
        if self.api_field not in details:
            logger.warning("No field '%s' in API game %s", self.api_field, details)
            return None
        if not details[self.api_field]:
            return None
        return self.url_pattern % details[self.api_field]

    def get_media_urls(self) -> dict[str, str]:
        """Return URLs for icons and logos from a service"""
        if self.source == "local":
            return {}
        service_games = ServiceGameCollection.get_for_service(self.service)
        medias: dict[str, str] = {}
        for game in service_games:
            if not game["details"]:
                continue
            details = json.loads(cast(str, game["details"]))
            media_url = self.get_media_url(details)
            if not media_url:
                continue
            medias[cast(str, game["slug"])] = media_url
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


class LogoOverlayMedia(ServiceMedia):
    """ServiceMedia that composites a game logo onto the downloaded artwork.

    The logo images are looked up in `logo_path`, using the artwork's file name with
    a `.png` extension; the file names are the game slugs, so both media types have to
    be downloaded with the same slug.

    This is applied by render(), which is called after all the media have been
    downloaded. Each artwork is only composited once per logo revision- a stamp file
    records which logo was composited, so repeated service reloads neither degrade
    the JPEG artwork nor waste time.
    """

    logo_path: str | None = None
    logo_max_size: tuple[int, int] | None = None  # None if this media is not an overlay target
    logo_y_position = 0.5  # Vertical position of the logo's center, 0.0 being the top edge
    logo_stamp_suffix = ".logo"

    @property
    def render_size(self) -> tuple[int, int]:
        """The size the artwork is rendered to; this is the size of the artwork file,
        which is not necessarily the size at which it is displayed."""
        return cast(tuple[int, int], self.size)

    def render(self):
        if not self.logo_max_size or not self.logo_path or not os.path.isdir(self.dest_path):
            return
        for filename in os.listdir(self.dest_path):
            if self._is_artwork(filename):
                self._render_filename(filename)

    @staticmethod
    def _is_artwork(filename: str) -> bool:
        """True if the file could be an image; this skips the logo stamp files."""
        return os.path.splitext(filename)[1].lower() in (".jpg", ".jpeg", ".png")

    def _render_filename(self, filename: str) -> None:
        art_path = os.path.join(self.dest_path, filename)
        logo_path = os.path.join(cast(str, self.logo_path), os.path.splitext(filename)[0] + ".png")
        if not os.path.exists(logo_path) or self._is_composited(art_path, logo_path):
            return
        try:
            with Image.open(logo_path) as logo_file:
                logo_image = logo_file.convert("RGBA")
            if not is_transparent_logo(logo_image):
                return
            with Image.open(art_path) as art_file:
                art_image = thumbnail_image(art_file.convert("RGBA"), self.render_size)
            art_image = paste_overlay(art_image, scale_to_fit(logo_image, self.logo_max_size), self.logo_y_position)
            art_image.convert("RGB").save(art_path)
        except Exception:  # pylint: disable=broad-except
            # Broken media must never break the service load.
            logger.warning("Could not composite logo on %s", filename, exc_info=True)
            return
        self._stamp_composited(art_path, logo_path)

    def _get_stamp_path(self, art_path: str) -> str:
        return art_path + self.logo_stamp_suffix

    def _is_composited(self, art_path: str, logo_path: str) -> bool:
        """True if this artwork was already composited with the current logo."""
        try:
            return os.path.getmtime(self._get_stamp_path(art_path)) >= os.path.getmtime(logo_path)
        except OSError:
            return False

    def _stamp_composited(self, art_path: str, logo_path: str) -> None:
        """Record the logo revision that has been composited on this artwork."""
        stamp_path = self._get_stamp_path(art_path)
        try:
            logo_mtime = os.path.getmtime(logo_path)
            Path(stamp_path).touch()
            os.utime(stamp_path, (logo_mtime, logo_mtime))
        except OSError:
            logger.warning("Could not write logo overlay stamp %s", stamp_path)
