"""Module for handling the PGA cache"""

import os
import shutil
from typing import Optional
from urllib.parse import urlparse

from lutris import settings
from lutris.util.log import logger
from lutris.util.system import merge_folders, path_contains


def get_cache_path(create: bool = False) -> str:
    """Returns the directory under which Lutris caches install files. This can be specified
    by the user, but defaults to a location in ~/.cache."""
    cache_path = get_custom_cache_path()
    if cache_path:
        cache_path = os.path.expanduser(cache_path)
        if os.path.isdir(cache_path) or os.path.isdir(os.path.dirname(cache_path)):
            return cache_path

    return settings.INSTALLER_CACHE_DIR


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


def get_custom_cache_path() -> Optional[str]:
    """Returns the custom path, wether it is usable or not. Returns
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

    cache_path = os.path.expanduser(cache_path)
    if not os.path.isdir(cache_path):
        parent = os.path.dirname(cache_path)
        if os.path.isdir(parent):
            logger.warning("Cache path %s does not exist, but its parent does so it can be created.", cache_path)
        else:
            logger.warning("Cache path %s does not exist", cache_path)
            return False

    return True


def save_custom_cache_path(path: str) -> None:
    """Saves the PGA cache path to the settings"""
    settings.write_setting("pga_cache_path", path)


def is_file_in_custom_cache(path: str) -> bool:
    """True if the 'path' is inside the custom cache (so we should
    not causally delete it). False for files in INSTALLER_CACHE_DIR -
    that is a cache, but not the custom cache, and we do delete those
    files freely."""
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
