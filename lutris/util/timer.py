import datetime


class Timer:

    def start_t(self):
        self.start = datetime.datetime.now()

    def end_t(self):
        self.end = datetime.datetime.now()

    def duration(self):
        return (self.end - self.start).seconds / 3600

    def increment(self, saved_dur):
        if saved_dur == '':
            return "%.1f hrs play time" % self.duration()

        saved_dur = float(saved_dur.split()[0])
        new_dur = saved_dur + self.duration()
        return "%.1f hrs play time" % new_dur
