"""The state of a long-running process, as a frontend displays it."""

from collections.abc import Callable

from lutris.util.log import logger


class ProgressInfo:
    """Contains the current state of a process being monitored. This can also provide
    for stopping the process via a function you can provide.

    Processes sometimes cannot be stopped after a certain point; at that point they start
    providing Progress objects with no stop-function."""

    def __init__(self, progress: float | None = 0, label_markup: str = "", stop_function: Callable | None = None):
        self.progress = progress
        self.label_markup = label_markup
        self.stop_function = stop_function
        self.has_ended = False

    @classmethod
    def ended(cls, label_markup: str = "") -> "ProgressInfo":
        """Creates a ProgressInfo whose has_ended flag is set, to indicate that
        the monitored process is over."""
        info = cls(1.0, label_markup=label_markup)
        info.has_ended = True
        return info

    @property
    def can_stop(self) -> bool:
        """Called to check if the stop button should appear."""
        return bool(self.stop_function)

    def stop(self):
        """Called whe the stop button is clicked."""
        if self.stop_function:
            try:
                self.stop_function()
            except Exception as ex:
                logger.exception("Error during progress box stop: %s", ex)
