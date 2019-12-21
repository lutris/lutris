"""Module for handling the PGA cache"""
import os
from lutris import settings


def get_cache_path():
    """Return the path of the PGA cache"""
    pga_cache_path = settings.read_setting("pga_cache_path")
    if pga_cache_path:
        return os.path.expanduser(pga_cache_path)


def save_cache_path(path):
    """Saves the PGA cache path to the settings"""
    settings.write_setting("pga_cache_path", path)
