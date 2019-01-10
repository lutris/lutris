"""Timer module"""
import datetime


class Timer:
    """Simple Timer class to time code"""

    def __init__(self):
        self._start = None
        self._end = None
        self.finished = False

    def start(self):
        """Starts the timer"""
        self._end = None
        self._start = datetime.datetime.now()
        self.finished = False

    def end(self):
        """Ends the timer"""
        self._end = datetime.datetime.now()
        self.finished = True

    @property
    def duration(self):
        """Return the total duration of the timer"""
        if not self._start:
            return 0

        if not self.finished:
            _duration = (datetime.datetime.now() - self._start).seconds
        else:
            _duration = (self._end - self._start).seconds

        return _duration
