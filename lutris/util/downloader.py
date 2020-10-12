import os
import time

import requests

from lutris import __version__
from lutris.util import jobs
from lutris.util.log import logger

# `time.time` can skip ahead or even go backwards if the current
# system time is changed between invocations. Use `time.monotonic`
# so we won't have screenshots making fun of us for showing negative
# download speeds.
get_time = time.monotonic


class Downloader:

    """Non-blocking downloader.

    Do start() then check_progress() at regular intervals.
    Download is done when check_progress() returns 1.0.
    Stop with cancel().
    """

    (INIT, DOWNLOADING, CANCELLED, ERROR, COMPLETED) = list(range(5))

    def __init__(self, url, dest, overwrite=False, referer=None, callback=None):
        self.url = url
        self.dest = dest
        self.overwrite = overwrite
        self.referer = referer
        self.stop_request = None
        self.thread = None
        self.callback = callback

        # Read these after a check_progress()
        self.state = self.INIT
        self.error = None
        self.downloaded_size = 0  # Bytes
        self.full_size = 0  # Bytes
        self.progress_fraction = 0
        self.progress_percentage = 0
        self.speed = 0
        self.average_speed = 0
        self.time_left = "00:00:00"  # Based on average speed

        self.last_size = 0
        self.last_check_time = 0
        self.last_speeds = []
        self.speed_check_time = 0
        self.time_left_check_time = 0
        self.file_pointer = None

    def start(self):
        """Start download job."""
        logger.debug("Starting download of:\n %s", self.url)
        self.state = self.DOWNLOADING
        self.last_check_time = get_time()
        if self.overwrite and os.path.isfile(self.dest):
            os.remove(self.dest)
        self.file_pointer = open(self.dest, "wb")
        self.thread = jobs.AsyncCall(self.async_download, self.on_done)
        self.stop_request = self.thread.stop_request

    def check_progress(self):
        """Append last downloaded chunk to dest file and store stats.

        :return: progress (between 0.0 and 1.0)"""
        if self.state not in [self.CANCELLED, self.ERROR]:
            self.get_stats()
        return self.progress_fraction

    def cancel(self):
        """Request download stop and remove destination file."""
        logger.debug("Download of %s cancelled", self.url)
        self.state = self.CANCELLED
        if self.stop_request:
            self.stop_request.set()
        if self.file_pointer:
            self.file_pointer.close()
            self.file_pointer = None
        if os.path.isfile(self.dest):
            os.remove(self.dest)

    def on_done(self, _result, error):
        if error:
            logger.error("Download failed: %s", error)
            self.state = self.ERROR
            self.error = error
            if self.file_pointer:
                self.file_pointer.close()
                self.file_pointer = None
            return

        if self.state == self.CANCELLED:
            return

        logger.debug("Finished downloading %s", self.url)
        if not self.downloaded_size:
            logger.warning("Downloaded file is empty")

        if not self.full_size:
            self.progress_fraction = 1.0
            self.progress_percentage = 100
        self.state = self.COMPLETED
        self.file_pointer.close()
        self.file_pointer = None
        if self.callback:
            self.callback()

    def async_download(self, stop_request=None):
        headers = requests.utils.default_headers()
        headers["User-Agent"] = "Lutris/%s" % __version__
        if self.referer:
            headers["Referer"] = self.referer
        response = requests.get(self.url, headers=headers, stream=True)
        if response.status_code != 200:
            logger.info("%s returned a %s error", self.url, response.status_code)
        response.raise_for_status()
        self.full_size = int(response.headers.get("Content-Length", "").strip() or 0)
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not self.file_pointer:
                break
            if chunk:
                self.downloaded_size += len(chunk)
                self.file_pointer.write(chunk)

    def get_stats(self):
        """Calculate and store download stats."""
        self.speed, self.average_speed = self.get_speed()
        self.time_left = self.get_average_time_left()
        self.last_check_time = get_time()
        self.last_size = self.downloaded_size

        if self.full_size:
            self.progress_fraction = float(self.downloaded_size) / float(self.full_size)
            self.progress_percentage = self.progress_fraction * 100

    def get_speed(self):
        """Return (speed, average speed) tuple."""
        elapsed_time = get_time() - self.last_check_time
        chunk_size = self.downloaded_size - self.last_size
        speed = chunk_size / elapsed_time or 1
        self.last_speeds.append(speed)

        # Average speed
        if get_time() - self.speed_check_time < 1:  # Minimum delay
            return self.speed, self.average_speed

        while len(self.last_speeds) > 20:
            self.last_speeds.pop(0)

        if len(self.last_speeds) > 7:
            # Skim extreme values
            samples = self.last_speeds[1:-1]
        else:
            samples = self.last_speeds[:]

        average_speed = sum(samples) / len(samples)

        self.speed_check_time = get_time()
        return speed, average_speed

    def get_average_time_left(self):
        """Return average download time left as string."""
        if not self.full_size:
            return "???"

        elapsed_time = get_time() - self.time_left_check_time
        if elapsed_time < 1:  # Minimum delay
            return self.time_left

        average_time_left = (self.full_size - self.downloaded_size) / self.average_speed
        minutes, seconds = divmod(average_time_left, 60)
        hours, minutes = divmod(minutes, 60)
        self.time_left_check_time = get_time()
        return "%d:%02d:%02d" % (hours, minutes, seconds)
