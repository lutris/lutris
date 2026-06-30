"""Module for handling the PGA cache"""

import os
import shutil
import time
from gettext import gettext as _
from urllib.parse import urlparse

from lutris import settings
from lutris.util.log import logger
from lutris.util.system import merge_folders, path_contains

INCOMPLETE_CACHE_SUFFIXES = (".tmp", ".progress")


def get_cache_path(create: bool = False) -> str:
    """Returns the directory under which Lutris caches install files. This can be specified
    by the user, but defaults to a location in ~/.cache."""
    cache_path = get_custom_cache_path()
    if cache_path:
        cache_path = os.path.expanduser(cache_path)
        if os.path.isdir(cache_path) or os.path.isdir(os.path.dirname(cache_path)):
            return cache_path

    return settings.INSTALLER_CACHE_DIR


def get_installer_cache_entries() -> list[dict[str, object]]:
    """Return cached installer folders with their size and file count."""
    cache_path = get_cache_path()
    if not os.path.isdir(cache_path):
        return []

    entries: list[dict[str, object]] = []
    for name in sorted(os.listdir(cache_path)):
        path = os.path.join(cache_path, name)
        if not os.path.isdir(path):
            continue

        size = 0
        file_count = 0
        for root, _dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith(".cache_lock"):
                    continue
                file_path = os.path.join(root, filename)
                try:
                    size += os.path.getsize(file_path)
                    file_count += 1
                except OSError:
                    pass

        entries.append({"name": name, "path": path, "size": size, "file_count": file_count})

    return entries


def delete_installer_cache_entry(path: str) -> None:
    """Delete one installer cache entry."""
    cache_path = get_cache_path()
    if os.path.islink(path):
        raise ValueError("Refusing to delete symlinked installer cache path: %s" % path)
    if not path_contains(cache_path, path, resolve_symlinks=True):
        raise ValueError("Refusing to delete path outside installer cache: %s" % path)
    if os.path.dirname(os.path.realpath(path)) != os.path.realpath(cache_path):
        raise ValueError("Refusing to delete nested path inside installer cache: %s" % path)
    if os.path.isdir(path):
        shutil.rmtree(path)


def get_incomplete_installer_cache_entries() -> list[dict[str, object]]:
    """Return incomplete installer download artifacts in the installer cache."""
    cache_path = get_cache_path()
    if not os.path.isdir(cache_path):
        return []

    entries: list[dict[str, object]] = []
    seen_paths = set()
    for root, _dirs, files in os.walk(cache_path):
        for filename in sorted(files):
            file_path = os.path.join(root, filename)
            if file_path in seen_paths:
                continue

            kind = None
            if filename.endswith(INCOMPLETE_CACHE_SUFFIXES):
                kind = _("Temporary download")
            elif filename.endswith(".cache_lock") and _is_orphaned_downloading_lock(file_path):
                kind = _("Stale download lock")

            if not kind:
                continue

            try:
                size = os.path.getsize(file_path)
                modified_at = os.path.getmtime(file_path)
            except OSError:
                size = 0
                modified_at = time.time()

            seen_paths.add(file_path)
            entries.append({"path": file_path, "size": size, "kind": kind, "modified_at": modified_at})

    return entries


def _is_orphaned_downloading_lock(lock_path: str) -> bool:
    """Return True if a cache lock belongs to an incomplete abandoned download."""
    data_path = lock_path[: -len(".cache_lock")]
    if os.path.exists(data_path):
        return False

    try:
        from lutris.util.download_cache import CacheState, get_cache_state

        return get_cache_state(data_path) == CacheState.DOWNLOADING
    except Exception:
        return False


def delete_incomplete_installer_cache_entries(paths: list[str]) -> None:
    """Delete incomplete installer download artifacts."""
    cache_path = get_cache_path()
    for path in paths:
        if os.path.islink(path):
            raise ValueError("Refusing to delete symlinked incomplete cache path: %s" % path)
        if not path_contains(cache_path, path, resolve_symlinks=True):
            raise ValueError("Refusing to delete path outside installer cache: %s" % path)
        if os.path.isfile(path):
            os.remove(path)


def get_url_cache_path(url: str, file_id: str, game_slug: str, prepare: bool = False) -> str:
    """Return the directory used as a cache a file that will be downloaded from
    a URL. You also provide the file id from the file list and the slug for
    the game.

    The files will be cached in a directory named after the slug, but
    in a further subdirectory for the file-id; since GOG file-ids are
    inconvenient for this, we special case URLs pointed to 'gog.com' here.

    If 'prepare' is true, this will also create the directory."""
    cache_path = get_cache_path()
    url_parts = urlparse(url)
    if url_parts.netloc.endswith("gog.com"):
        folder = "gog"
    else:
        folder = file_id
    path = os.path.join(cache_path, game_slug, folder)

    if prepare:
        if not os.path.exists(path):
            os.makedirs(path)

    return path


def get_custom_cache_path() -> str | None:
    """Returns the custom path, whether it is usable or not. Returns
    None if the path is not set, so that the default INSTALLER_CACHE_DIR
    should be used."""
    cache_path = settings.read_setting("pga_cache_path")
    return cache_path if cache_path else None


def has_valid_custom_cache_path() -> bool:
    """True if the custom cache path is set and refers to a usable
    directory, so that get_cache_path() will return it. The directory
    does not have to exist for this, but at least its *parent* directory
    does."""
    cache_path = get_custom_cache_path()
    if not cache_path:
        return False

    valid, msg = validate_custom_cache_path(cache_path)
    if msg:
        logger.warning(msg)

    return valid


def validate_custom_cache_path(cache_path: str) -> tuple[bool, str | None]:
    """Checks the validity of a given path; returns a flag for whether
    it can be used, and an optional message for what's wrong with it,
    if anything is."""
    cache_path = os.path.expanduser(cache_path)
    if not os.path.isdir(cache_path):
        parent = os.path.dirname(cache_path)
        if os.path.isdir(parent):
            return True, _(
                "The cache path '%s' does not exist, but its parent does so it will be created when needed."
            ) % cache_path
        else:
            return False, _(
                "The cache path %s does not exist, nor does its parent, so it won't be created."
            ) % cache_path

    return True, None


def save_custom_cache_path(path: str) -> None:
    """Saves the PGA cache path to the settings"""
    settings.write_setting("pga_cache_path", path)


def is_file_in_custom_cache(path: str) -> bool:
    """True if the 'path' is inside the custom cache (so we should
    not casually delete it). False for files in INSTALLER_CACHE_DIR -
    that is a cache, but not the custom cache, and Lutris manages
    the lifecycle of those files itself (cleaning up after successful
    installs, but preserving them after failures for retry)."""
    cache_path = get_custom_cache_path()
    return bool(cache_path and path_contains(cache_path, path))


def save_to_cache(source: str, destination: str) -> None:
    """Copy a file or folder to the cache"""
    if not source:
        raise ValueError("Missing source")
    if os.path.dirname(source) == destination:
        logger.info("File %s is already cached in %s", source, destination)
        return
    if os.path.isdir(source):
        # Copy folder recursively
        merge_folders(source, destination)
    else:
        shutil.copy(source, destination)
    logger.debug("Cached %s to %s", source, destination)
