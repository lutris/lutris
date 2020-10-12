"""Module for handling the PGA cache"""
import os
import shutil

from lutris import settings
from lutris.util.log import logger
from lutris.util.system import merge_folders


def get_cache_path():
    """Return the path of the PGA cache"""
    pga_cache_path = settings.read_setting("pga_cache_path")
    if pga_cache_path:
        return os.path.expanduser(pga_cache_path)
    return None


def save_cache_path(path):
    """Saves the PGA cache path to the settings"""
    settings.write_setting("pga_cache_path", path)


def save_to_cache(source, destination):
    """Copy a file or folder to the cache"""
    if not source:
        raise ValueError("No source given to save")
    if os.path.dirname(source) == destination:
        logger.info("File is already cached in %s, skipping", destination)
        return
    if os.path.isdir(source):
        # Copy folder recursively
        merge_folders(source, destination)
    else:
        shutil.copy(source, destination)
    logger.debug("Copied %s to cache %s", source, destination)
