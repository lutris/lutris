"""Module for handling the PGA cache"""

import os
import shutil
from typing import Optional

from lutris import settings
from lutris.util.log import logger
from lutris.util.system import merge_folders


def get_cache_path(create: bool = False) -> str:
    """Returns the directory under which Lutris caches install files. This can be specified
    by the user, but defaults to a location in ~/.cache."""
    cache_path = get_custom_cache_path()
    if cache_path:
        cache_path = os.path.expanduser(cache_path)
        if os.path.isdir(cache_path):
            return cache_path

    return settings.INSTALLER_CACHE_DIR


def get_custom_cache_path() -> Optional[str]:
    """Returns the custom path, wether it is usable or not. Returns
    None if the path is not set, so that the default INSTALLER_CACHE_DIR
    should be used."""
    cache_path = settings.read_setting("pga_cache_path")
    return cache_path if cache_path else None


def has_valid_custom_cache_path() -> bool:
    """True if the custom cache path is set and refers to a usable
    directory."""
    cache_path = get_custom_cache_path()
    if not cache_path:
        return False

    cache_path = os.path.expanduser(cache_path)
    if not os.path.isdir(cache_path):
        logger.warning("Cache path %s does not exist", cache_path)
        return False

    return True


def save_custom_cache_path(path: str) -> None:
    """Saves the PGA cache path to the settings"""
    settings.write_setting("pga_cache_path", path)


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
