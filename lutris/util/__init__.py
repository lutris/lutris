"""Misc common functions"""

import functools
from typing import Any, Callable, Mapping

AnyCallable = Callable[..., Any]


def selective_merge(base_obj: Any, delta_obj: Mapping[Any, Any]) -> Mapping[Any, Any]:
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


class cache_single:
    """A simple replacement for lru_cache, with no LRU behavior. This caches
    a single result from a function that has no arguments at all. Exceptions
    are not cached; there's a 'clear_cache()' function on the wrapper like with
    lru_cache to explicitly clear the cache."""

    def __init__(self, function: AnyCallable):
        functools.update_wrapper(self, function)
        self.function = function
        self.is_cached = False
        self.cached_item = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if args or kwargs:
            return self.function(*args, **kwargs)

        if not self.is_cached:
            self.cached_item = self.function()
            self.is_cached = True

        return self.cached_item

    def cache_clear(self) -> None:
        self.is_cached = False
        self.cached_item = None
