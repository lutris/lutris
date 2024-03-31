"""Timer module"""

# Standard Library
import time


class Timer:
    """Simple Timer class to time code"""

    def __init__(self):
        self._start = None
        self._end = None
        self.finished = False

    def start(self):
        """Starts the timer"""
        self._end = None
        self._start = time.monotonic()
        self.finished = False

    def end(self):
        """Ends the timer"""
        self._end = time.monotonic()
        self.finished = True

    @property
    def duration(self):
        """Return the total duration of the timer"""
        if not self._start:
            return 0

        if not self.finished:
            _duration = time.monotonic() - self._start
        else:
            _duration = self._end - self._start

        return _duration
