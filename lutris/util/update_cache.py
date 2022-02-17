"""Manage a cache file of execution times for updates"""
import json
import os
from datetime import datetime

from lutris import settings

UPDATE_CACHE_PATH = os.path.join(settings.CACHE_DIR, "updates.json")
DATE_FORMAT = "%d/%m/%Y %H:%M:%S"


def write_date_to_cache(key):
    """Write current time to the cache for 'key'"""
    cache = _read_cache_content()
    cache[key] = datetime.strftime(datetime.now(), DATE_FORMAT)
    with open(UPDATE_CACHE_PATH, "w", encoding='utf-8') as json_file:
        json.dump(cache, json_file, indent=2)


def remove_date_from_cache(key):
    """Deletes a datetime object for 'key'"""
    cache = _read_cache_content()
    cache.pop(key, None)
    with open(UPDATE_CACHE_PATH, "w", encoding='utf-8') as json_file:
        json.dump(cache, json_file, indent=2)


def _read_cache_content():
    """Return the content of the cache"""
    if not os.path.exists(UPDATE_CACHE_PATH):
        return {}
    with open(UPDATE_CACHE_PATH, "r", encoding='utf-8') as json_file:
        cache = json.load(json_file)
    return cache


def read_date_from_cache(key):
    """Return a datetime object from 'key'"""
    cache = _read_cache_content()
    date = cache.get(key)
    if not date:
        return
    date = datetime.strptime(date, DATE_FORMAT)
    return date


def get_last_call(key):
    """Return the time in second since the last update for 'key' was made"""
    date = read_date_from_cache(key)
    if not date:
        return 0
    delta = datetime.now() - date
    return delta.seconds
