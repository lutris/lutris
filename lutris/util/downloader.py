import bisect
import os
import threading
import time
from typing import Any, Dict, Optional

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

    def __init__(
        self,
        url: str,
        dest: str,
        overwrite: bool = False,
        referer: Optional[str] = None,
        cookies: Any = None,
        headers: Dict[str, str] = None,
    ) -> None:
        self.url: str = url
        self.dest: str = dest
        self.cookies = cookies
        self.headers = headers
        self.overwrite: bool = overwrite
        self.referer = referer
        self.stop_request = None
        self.thread = None

        # Read these after a check_progress()
        self.state = self.INIT
        self.error = None
        self.downloaded_size: int = 0  # Bytes
        self.full_size: int = 0  # Bytes
        self.progress_fraction: float = 0
        self.progress_percentage: float = 0
        self.average_speed = 0
        self.time_left: str = "00:00:00"  # Based on average speed
        self.last_size: int = 0
        self.last_check_time: float = 0.0
        self.last_speeds = []
        self.speed_check_time = 0
        self.time_left_check_time = 0
        self.file_pointer = None
        self.progress_event = threading.Event()

    def __repr__(self):
        return "downloader for %s" % self.url

    def start(self):
        """Start download job."""
        logger.debug("⬇ %s", self.url)
        self.state = self.DOWNLOADING
        self.last_check_time = get_time()
        if self.overwrite and os.path.isfile(self.dest):
            os.remove(self.dest)
        self.file_pointer = open(self.dest, "wb")  # pylint: disable=consider-using-with
        self.thread = jobs.AsyncCall(self.async_download, None)
        self.stop_request = self.thread.stop_request

    def reset(self):
        """Reset the state of the downloader"""
        self.state = self.INIT
        self.error = None
        self.downloaded_size = 0  # Bytes
        self.full_size = 0  # Bytes
        self.progress_fraction = 0
        self.progress_percentage = 0
        self.average_speed = 0
        self.time_left = "00:00:00"  # Based on average speed
        self.last_size = 0
        self.last_check_time = 0.0
        self.last_speeds = []
        self.speed_check_time = 0
        self.time_left_check_time = 0
        self.file_pointer = None

    def check_progress(self, blocking=False):
        """Append last downloaded chunk to dest file and store stats.

        blocking: if true and still downloading, block until some progress is made.
        :return: progress (between 0.0 and 1.0)"""
        if blocking and self.state in [self.INIT, self.DOWNLOADING] and self.progress_fraction < 1.0:
            self.progress_event.wait()
            self.progress_event.clear()

        if self.state not in [self.CANCELLED, self.ERROR]:
            self.get_stats()
        return self.progress_fraction

    def join(self, progress_callback=None):
        """Blocks waiting for the download to complete.

        'progress_callback' is invoked repeatedly as the download
        proceeds, if given, and is passed the downloader itself.

        Returns True on success, False if cancelled."""
        while self.state == self.DOWNLOADING:
            self.check_progress(blocking=True)
            if progress_callback:
                progress_callback(self)

        if self.error:
            raise self.error
        return self.state == self.COMPLETED

    def cancel(self):
        """Request download stop and remove destination file."""
        logger.debug("❌ %s", self.url)
        self.state = self.CANCELLED
        if self.stop_request:
            self.stop_request.set()
        if self.file_pointer:
            self.file_pointer.close()
            self.file_pointer = None
        if os.path.isfile(self.dest):
            os.remove(self.dest)

    def async_download(self):
        try:
            headers = requests.utils.default_headers()
            headers["User-Agent"] = "Lutris/%s" % __version__
            if self.referer:
                headers["Referer"] = self.referer
            if self.headers:
                for key, value in self.headers.items():
                    headers[key] = value
            response = requests.get(self.url, headers=headers, stream=True, timeout=30, cookies=self.cookies)
            if response.status_code != 200:
                logger.info("%s returned a %s error", self.url, response.status_code)
            response.raise_for_status()
            self.full_size = int(response.headers.get("Content-Length", "").strip() or 0)
            self.progress_event.set()
            for chunk in response.iter_content(chunk_size=8192):
                if not self.file_pointer:
                    break
                if chunk:
                    self.downloaded_size += len(chunk)
                    self.file_pointer.write(chunk)
                self.progress_event.set()
            self.on_download_completed()
        except Exception as ex:
            logger.exception("Download failed: %s", ex)
            self.on_download_failed(ex)

    def on_download_failed(self, error: Exception):
        # Cancelling closes the file, which can result in an
        # error. If so, we just remain cancelled.
        if self.state != self.CANCELLED:
            self.state = self.ERROR
            self.error = error
        if self.file_pointer:
            self.file_pointer.close()
            self.file_pointer = None

    def on_download_completed(self):
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

    def get_stats(self):
        """Calculate and store download stats."""
        self.average_speed = self.get_speed()
        self.time_left = self.get_average_time_left()
        self.last_check_time = get_time()
        self.last_size = self.downloaded_size

        if self.full_size:
            self.progress_fraction = float(self.downloaded_size) / float(self.full_size)
            self.progress_percentage = self.progress_fraction * 100

    def get_speed(self):
        """Return the average speed of the download so far."""
        elapsed_time = get_time() - self.last_check_time
        if elapsed_time > 0:
            chunk_size = self.downloaded_size - self.last_size
            speed = chunk_size / elapsed_time or 1
            # insert in sorted order, so we can omit the least and
            # greatest value later
            bisect.insort(self.last_speeds, speed)

        # Until we get the first sample, just return our default
        if not self.last_speeds:
            return self.average_speed

        if get_time() - self.speed_check_time < 1:  # Minimum delay
            return self.average_speed

        while len(self.last_speeds) > 20:
            self.last_speeds.pop(0)

        if len(self.last_speeds) > 7:
            # Skip extreme values
            samples = self.last_speeds[1:-1]
        else:
            samples = self.last_speeds[:]

        average_speed = sum(samples) / len(samples)

        self.speed_check_time = get_time()
        return average_speed

    def get_average_time_left(self) -> str:
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
