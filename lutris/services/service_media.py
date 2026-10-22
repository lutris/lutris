import json
import os
import random
import time
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, cast

from lutris.database.services import ServiceGameCollection
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


def media_path_exists(media_path: MediaPath) -> bool:
    """Returns True if the media file exists and has contents. This is a stand-alone function
    so that a caller that checks many paths can substitute a memoizing version, since each
    check costs a couple of file system calls."""
    return media_path.exists


class MediaPaths(list[MediaPath]):
    """The paths where a game's media may be found, in priority order.

    This is a list, so it can be stored in the game store and handled like one, but it also
    remembers which of its paths it resolved to. The views re-render the same row over and
    over, and resolving the media path stats the file system each time, so we cache the
    resolution and recompute it only when the caller's media cache generation number changes.
    """

    def __init__(self, paths: Iterable[MediaPath] = ()) -> None:
        super().__init__(paths)
        self._resolved_generation = -1
        self._resolved_media_path: MediaPath | None = None

    def get_resolved(self, generation: int) -> MediaPath | None:
        """Returns the media path to display for this game, which is resolve_media_path() of
        this list, but computed at most once per media cache generation.

        Media files are added and removed outside of Lutris, so the cached resolution is
        discarded whenever the generation number changes; that happens when media is
        downloaded or replaced."""
        if generation != self._resolved_generation:
            self._resolved_media_path = resolve_media_path(self) if self else None
            self._resolved_generation = generation
        return self._resolved_media_path


_media_instances: dict[type, "ServiceMedia"] = {}


def get_media_instance(media_class: type["ServiceMedia"]) -> "ServiceMedia":
    """Returns the shared instance of a media class, creating it the first time it's needed.

    A ServiceMedia object describes a kind of media and holds no per-game state, but creating
    one checks- and if necessary creates- its destination directory. The fallback search below
    needs one of each kind for every game it has to handle, so they are created once instead.
    """
    instance = _media_instances.get(media_class)
    if instance is None:
        instance = _media_instances[media_class] = media_class()
    return instance


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

    def get_fallback_media_path(
        self,
        services: Iterable[tuple["BaseService", Callable[[], str]]],
        exists_function: Callable[[MediaPath], bool] | None = None,
    ) -> MediaPath | None:
        """Returns the media path to use when none of the possible paths (above) actually exist.
        This may be scaled down so it no taller than this media's height.

        This method finds the media that is nearest to the size of this media, and
        then evaluates the provided callables to obtain slugs, starting with the nearest
        match. As soon as it finds a media that exists, it will return it. If it finds
        none, it returns None.

        The optional exists_function replaces the file system check made on each candidate
        media; a caller that checks many games at once can pass a memoizing version.
        """

        medias = [(get_media_instance(media_class), t[1]) for t in services for media_class in t[0].medias.values()]
        exists = exists_function or media_path_exists

        def similarity(media: tuple[ServiceMedia, Callable[[], str]]) -> int:
            diff = abs(media[0].size[1] - self.size[1])
            return diff if media[0].size[1] >= self.size[1] else diff + 1000

        # A slug function may run a database query, and each one appears once per media class,
        # so evaluate each of them at most once per search.
        slugs: dict[int, str | None] = {}

        def get_slug(slug_function: Callable[[], str]) -> str | None:
            key = id(slug_function)
            if key not in slugs:
                slugs[key] = slug_function()
            return slugs[key]

        for media, slug_function in sorted(medias, key=similarity):
            if media.can_be_fallback:
                slug = get_slug(slug_function)
                if slug:
                    for mp in media.get_possible_media_paths(slug):
                        if exists(mp):
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
