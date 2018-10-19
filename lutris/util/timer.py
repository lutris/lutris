import datetime
import os.path

class Timer:

    def start_t(self):
        self.start = datetime.datetime.now().replace(microsecond=0)

    def end_t(self):
        self.end = datetime.datetime.now().replace(microsecond=0)

    def duration(self):
        return self.end - self.start