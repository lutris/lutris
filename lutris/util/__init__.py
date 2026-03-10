"""Misc common functions"""

import functools
from typing import Any, Callable, Generic, Mapping, Optional, TypeVar, cast

AnyCallable = Callable[..., Any]
DecoratedResult = TypeVar("DecoratedResult")


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


class cache_single(Generic[DecoratedResult]):
    """A simple replacement for lru_cache, with no LRU behavior. This caches
    a single result from a function that has no arguments at all. Exceptions
    are not cached; there's a 'clear_cache()' function on the wrapper like with
    lru_cache to explicitly clear the cache."""

    def __init__(self, function: Callable[..., DecoratedResult]):
        functools.update_wrapper(self, function)
        self.function = function
        self.is_cached = False
        self.cached_item = None

    def __call__(self, *args: Any, **kwargs: Any) -> DecoratedResult:
        if args or kwargs:
            return self.function(*args, **kwargs)

        if not self.is_cached:
            self.cached_item = self.function()
            self.is_cached = True

        return cast(DecoratedResult, self.cached_item)

    def cache_clear(self) -> None:
        self.is_cached = False
        self.cached_item = None


def async_choices(
    generate: AnyCallable,
    ready: Callable[[], bool],
    invalidate: Optional[Callable[[], None]] = None,
    error_message: str = "Failed to load choices",
) -> Callable[[AnyCallable], AnyCallable]:
    """Decorator that wraps a choices callable with async background loading support.

    When the decorated function is called and ready() returns False, starts an AsyncCall to run
    generate() on a worker thread and returns [] immediately. When the worker completes,
    register_reload_callback() callbacks are fired on the UI thread so comboboxes can repopulate
    in place. When ready() returns True, calls through to the original function normally.

    Adds to the decorated function:
    - register_reload_callback: used by widget_generator to register combobox refresh callbacks

    See widget_generator._generate_choice() for how register_reload_callback is used.
    """

    def decorator(choices_func: AnyCallable) -> AnyCallable:
        @functools.wraps(choices_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not ready():
                from lutris.util.jobs import AsyncCall

                AsyncCall(generate, _on_loaded)  # type: ignore[no-untyped-call]
                return []
            return choices_func(*args, **kwargs)

        wrapper._reload_callbacks = []  # type: ignore[attr-defined]
        wrapper.register_reload_callback = (  # type: ignore[attr-defined]
            lambda callback: wrapper._reload_callbacks.append(callback)  # type: ignore[attr-defined]
        )

        def _on_loaded(result: Any, error: Any) -> None:
            from lutris.util.log import logger

            if error:
                logger.exception("%s: %s", error_message, error)
            elif result:
                if invalidate is not None:
                    invalidate()
                for callback in wrapper._reload_callbacks:  # type: ignore[attr-defined]
                    callback()
            wrapper._reload_callbacks.clear()  # type: ignore[attr-defined]

        return wrapper

    return decorator
