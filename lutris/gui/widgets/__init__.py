from typing import Callable, Dict, List, Optional, Tuple

from lutris.util.jobs import schedule_at_idle


class NotificationRegistration:
    """Represents a registered callback; can be used to remove the registration. Obtain this
    by calling NotificationSource.register; a null-object that represent no registration
    can be obtained via EMPTY_NOTIFICATION_REGISTRATION."""

    def __init__(self, notification_source: Optional["NotificationSource"], callback_id: int) -> None:
        self.notification_source = notification_source
        self.callback_id = callback_id

    @property
    def is_registered(self):
        """True if this registration is still registered; if false it has been unregistered and
        won't fire anymore."""
        return self.notification_source and self.callback_id in self.notification_source._callbacks

    def unregister(self) -> None:
        """Unregisters a callback that register() had registered."""
        if self.notification_source:
            self.notification_source._callbacks.pop(self.callback_id, None)
            self.notification_source = None


# A singleton registration that is already unregistered; used as a null object
# rather than None, so you can omit the checks for None,
EMPTY_NOTIFICATION_REGISTRATION = NotificationRegistration(None, 0)


class NotificationSource:
    """A class to inform interested code of changes in a global, like a signal but not attached to any
    object."""

    def __init__(self) -> None:
        self._generation_number = 0
        self._callbacks: Dict[int, Callable] = {}
        self._next_callback_id = 1
        self._scheduled_callbacks: List[Tuple[Callable, Tuple, Dict]] = []

    @property
    def has_handlers(self) -> bool:
        """True if any handlers are registered."""
        return bool(self._callbacks)

    def fire(self, *args, **kwargs) -> None:
        """Signals that the thing, whatever it is, has happened. This increments the generation number,
        and schedules the callbacks to run (if they are not scheduled already)."""
        self._generation_number += 1
        for callback in self._callbacks.values():
            self._scheduled_callbacks.append((callback, args, kwargs))
        schedule_at_idle(self._notify)

    @property
    def generation_number(self) -> int:
        """Returns a number that is incremented on each call to fire(). This can be polled
        passively, when registering a callback is inappropriate."""
        return self._generation_number

    def register(self, callback: Callable) -> NotificationRegistration:
        """Registers a callback to be called after the thing, whatever it is, has happened;
        fire() schedules callbacks to be called at idle time on the main thread.

        Note that a callback will be kept alive until unregistered, and this can keep
        large objects alive until then.

        Returns registration object to use to unregister the callback."""

        # We still use callback ID numbers to avoid creating a circular reference.
        callback_id = self._next_callback_id
        self._callbacks[callback_id] = callback
        self._next_callback_id += 1
        return NotificationRegistration(self, callback_id)

    def _notify(self):
        while self._scheduled_callbacks:
            callback, args, kwargs = self._scheduled_callbacks.pop(0)
            callback(*args, **kwargs)
