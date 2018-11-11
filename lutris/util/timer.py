import datetime


class Timer:
    """Simple Timer class to time code.
    You can overload the + operator according to your need by using a new timer_type.
    """

    def __init__(self, timer_type=None):
        self.timer_type = timer_type
        self.finsihed = False

    def start_t(self):
        self._start = datetime.datetime.now()

    def end_t(self):
        self._end = datetime.datetime.now()
        self.finsihed = True

    def duration(self):
        return (self._end - self._start).seconds / 3600

    def __add__(self, saved_dur):
        # 'result' intended for future use when there are other timer_type
        result = None
        if self.timer_type == "playtime":
            saved_dur = float(saved_dur.split()[0])
            new_dur = saved_dur + self.duration()
            result = "%.1f hrs" % new_dur

        return result
