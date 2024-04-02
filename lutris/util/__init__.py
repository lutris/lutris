"""Misc common functions"""

from functools import wraps


def selective_merge(base_obj, delta_obj):
    """used by write_json"""
    if not isinstance(base_obj, dict):
        return delta_obj
    common_keys = set(base_obj).intersection(delta_obj)
    new_keys = set(delta_obj).difference(common_keys)
    for k in common_keys:
        base_obj[k] = selective_merge(base_obj[k], delta_obj[k])
    for k in new_keys:
        base_obj[k] = delta_obj[k]
    return base_obj


def cache_single(function):
    """A simple replacement for lru_cache, with no LRU behavior. This caches
    a single result from a function that has no arguments at all. Exceptions
    are not cached; there's a 'clear_cache()' function on the wrapper like with
    lru_cache to explicitly clear the cache."""
    is_cached = False
    cached_item = None

    @wraps(function)
    def wrapper(*args, **kwargs):
        nonlocal is_cached, cached_item
        if args or kwargs:
            return function(*args, **kwargs)

        if not is_cached:
            cached_item = function()
            is_cached = True

        return cached_item

    def cache_clear():
        nonlocal is_cached, cached_item
        is_cached = False
        cached_item = None

    wrapper.cache_clear = cache_clear
    return wrapper
