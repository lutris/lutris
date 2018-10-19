import datetime

def sec_to_hrs(dur):
    return dur/3600


class Timer:

    def start_t(self):
        self.start = datetime.datetime.now().replace(microsecond=0)

    def end_t(self):
        self.end = datetime.datetime.now().replace(microsecond=0)

    def duration(self):
        return (self.end - self.start).seconds

    def increment(self, saved_dur):
        if saved_dur == '':
            return "%.1f hrs play time" % sec_to_hrs(self.duration())

        saved_dur = float(saved_dur.split()[0])
        new_dur = saved_dur + sec_to_hrs(self.duration())
        return "%.1f hrs play time" % new_dur
