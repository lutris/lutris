import datetime
import os.path


def clock_look(dur):
    if dur < 60:
        return ''
    if 60 < dur < 3600:
        mins = int(dur/60)
        return "00:%02d" % mins
    
    hrs = int(dur / 3600)
    tmp = dur % 3600
    mins = int(tmp / 60)
    return "%02d:%02d" % hrs, mins


class Timer:

    def start_t(self):
        self.start = datetime.datetime.now().replace(microsecond=0)

    def end_t(self):
        self.end = datetime.datetime.now().replace(microsecond=0)

    def duration(self):
        return (self.end - self.start).seconds

    def increment(self, saved_dur):
        if saved_dur == '':
            return clock_look(self.duration())
        
        saved_hrs, saved_min = saved_dur.split(':')
        saved_dur = datetime.timedelta(
            hours=int(saved_hrs), minutes=int(saved_min))
        return clock_look(saved_dur.seconds + self.duration())
