"""Timer module"""

# Standard Library
import time


class Timer:
    """Simple Timer class to time code"""

    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None
        self.finished = False

    def start(self) -> None:
        """Starts the timer"""
        self._end = None
        self._start = time.monotonic()
        self.finished = False

    def end(self) -> None:
        """Ends the timer"""
        self._end = time.monotonic()
        self.finished = True

    @property
    def duration(self) -> float:
        """Return the total duration of the timer"""
        if self._start is None:
            return 0.0

        if not self.finished or self._end is None:
            return time.monotonic() - self._start

        return self._end - self._start
