import datetime


class Timer:
    """Simple Timer class to time code"""

    def __init__(self, format="hours"):
        self.format = format
        self._start = None
        self._end = None
        self.finished = False

    def start(self):
        self._end = None
        self._start = datetime.datetime.now()
        self.finished = False

    def end(self):
        self._end = datetime.datetime.now()
        self.finished = True

    @property
    def duration(self):
        if not self._start:
            dur = 0

        elif not self.finished:
            now = datetime.datetime.now()
            dur = (now - self._start).seconds

        else:
            dur = (self._end - self._start).seconds

        return self._convert_time(dur)

    def _convert_time(self, dur):
        if self.format == "seconds":
            return dur
        if self.format == "minutes":
            return dur / 60
        if self.format == "hours":
            return dur / 3600
        if self.format == "days":
            return dur / 86400
