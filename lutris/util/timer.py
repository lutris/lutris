import datetime


class Timer:
    """Simple Timer class to time code"""

    def __init__(self, format):
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
            result = 0

        elif not self.finished:
            now = datetime.datetime.now()
            result = (now - self._start).seconds

        else:
            result = (self._end - self._start).seconds

        # Retrun time in the specified format
        if self.format == 'seconds':
            return result
        if self.format == 'minutes':
            return result / 60
        if self.format == 'hours':
            return result / 3600
        if self.format == 'days':
            return result / 86400
