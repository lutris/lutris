import abc
import bisect
import os
import threading
import time
from collections.abc import Callable
from typing import Any

import requests

from lutris import __version__
from lutris.util import jobs
from lutris.util.log import logger

# `time.time` can skip ahead or even go backwards if the current
# system time is changed between invocations. Use `time.monotonic`
# so we won't have screenshots making fun of us for showing negative
# download speeds.
get_time = time.monotonic

# Default chunk size for downloads (512KB).
# Previously 8KB which caused excessive syscall overhead.
# 512KB matches heroic-gogdl and provides good throughput
# while keeping memory usage reasonable.
DEFAULT_CHUNK_SIZE = 1024 * 512  # 512KB


class DownloadStallError(Exception):
    """Raised when a download connection stalls below the speed threshold.

    Carries diagnostic information about the stall for logging and retry
    decisions.
    """

    def __init__(self, throughput: float, duration: float) -> None:
        self.throughput = throughput  # bytes/second at time of detection
        self.duration = duration  # seconds the connection was below threshold
        super().__init__("Download stalled: %.1f B/s for %.1f seconds" % (throughput, duration))


class StallMonitor:
    """Tracks throughput for a single download stream and detects stalls.

    A monitor holds a mutable throughput window (the time and byte count at
    which the current window opened). This state is *not* safe to share
    between threads: each stream — including each parallel worker in
    GOGDownloader — must use its own StallMonitor, otherwise one stream's
    byte counter pollutes another's window and produces nonsensical
    (even negative) throughput readings.
    """

    def __init__(self, low_speed_limit: int, low_speed_time: int) -> None:
        self.low_speed_limit = low_speed_limit  # bytes/second
        self.low_speed_time = low_speed_time  # seconds below threshold before triggering
        self.window_start: float | None = None  # monotonic time when speed first dropped
        self.bytes_at_window_start: int = 0  # stream bytes when the window opened

    def check(self, bytes_received_total: int) -> None:
        """Check if the stream has stalled and raise DownloadStallError if so.

        Tracks a rolling throughput window. When throughput drops below
        ``low_speed_limit`` for longer than ``low_speed_time``, raises
        DownloadStallError to trigger a retry.

        Args:
            bytes_received_total: Total bytes received so far on *this*
                stream. Must come from a counter owned by the calling
                stream, never a value shared across workers.
        """
        now = get_time()

        if self.window_start is None:
            # Not currently in a stall window — start one
            self.window_start = now
            self.bytes_at_window_start = bytes_received_total
            return

        elapsed = now - self.window_start
        if elapsed <= 0:
            return

        bytes_in_window = bytes_received_total - self.bytes_at_window_start
        throughput = bytes_in_window / elapsed

        if throughput >= self.low_speed_limit:
            # Speed is good — reset the window
            self.window_start = now
            self.bytes_at_window_start = bytes_received_total
            return

        # Speed is below threshold — check if we've exceeded the time limit
        if elapsed >= self.low_speed_time:
            raise DownloadStallError(throughput=throughput, duration=elapsed)


class BaseDownloader(abc.ABC):
    """Non-blocking downloader framework — the public interface.

    Do start() then check_progress() at regular intervals.
    Download is done when check_progress() returns 1.0.
    Stop with cancel().

    This base owns everything that is independent of *how* the bytes are
    fetched: the state machine, progress/speed statistics, the retry loop,
    and stall-detection configuration. Concrete subclasses (SimpleDownloader,
    GOGDownloader) implement the actual transfer in async_download() and
    release any transfer-specific resources in _release_resources().
    """

    (INIT, DOWNLOADING, CANCELLED, ERROR, COMPLETED) = list(range(5))

    # Stall detection thresholds (matches lgogdownloader defaults)
    LOW_SPEED_LIMIT = 200  # bytes/second
    LOW_SPEED_TIME = 30  # seconds below threshold before triggering
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds between retries

    def __init__(
        self,
        url: str,
        dest: str,
        overwrite: bool = False,
        referer: str | None = None,
        cookies: Any = None,
        headers: dict[str, str] | None = None,
        session: requests.Session | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self.url: str = url
        self.dest: str = dest
        self.cookies = cookies
        self.headers = headers
        self.overwrite: bool = overwrite
        self.referer = referer
        self.session = session
        self.chunk_size = chunk_size
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
        self.progress_event = threading.Event()

    def __repr__(self):
        return "downloader for %s" % self.url

    @property
    def _log_name(self) -> str:
        """Identifier used in lifecycle log lines.

        Subclasses can override to surface details (e.g. GOG's worker count)
        so log-grepping for a given download mode keeps working."""
        return self.url

    def _new_stall_monitor(self) -> StallMonitor:
        """Create a fresh stall monitor for a single download stream.

        Each stream must own its monitor — see StallMonitor — so this is a
        factory rather than shared state on the downloader.
        """
        return StallMonitor(self.LOW_SPEED_LIMIT, self.LOW_SPEED_TIME)

    def start(self):
        """Start the download on a background thread."""
        logger.debug("⬇ %s", self._log_name)
        self.state = self.DOWNLOADING
        self.last_check_time = get_time()
        self._prepare_destination()
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

    def join(self, progress_callback: Callable[["BaseDownloader"], None] | None = None) -> bool:
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
        logger.debug("❌ %s", self._log_name)
        self.state = self.CANCELLED
        if self.stop_request:
            self.stop_request.set()
        self._release_resources()
        # The user gave up on this download — drop any resumable state too.
        self._discard_persistent_state()
        if os.path.isfile(self.dest):
            os.remove(self.dest)

    # ------------------------------------------------------------------
    # Transfer hooks — implemented by concrete downloaders
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _prepare_destination(self) -> None:
        """Prepare the destination before the transfer thread starts.

        Called on the calling thread from start(). Subclasses set up whatever
        the transfer needs (e.g. opening the output file)."""

    @abc.abstractmethod
    def async_download(self) -> None:
        """Run the transfer to completion on the background thread.

        Implementations must drive the download, then call
        on_download_completed() on success or on_download_failed() on error."""

    def _release_resources(self) -> None:  # noqa: B027
        """Release transient transfer resources (e.g. an open file handle).

        Called on every terminal path — completion, failure, and cancel. The
        default does nothing; subclasses override when they hold resources."""

    def _discard_persistent_state(self) -> None:  # noqa: B027
        """Drop on-disk state that would let the download resume later.

        Called only on completion and cancel — NOT on failure, where the state
        is deliberately kept so the next attempt can resume. The default does
        nothing; subclasses with resumable progress override it."""

    def on_download_failed(self, error: Exception):
        # Cancelling closes the file, which can result in an
        # error. If so, we just remain cancelled.
        if self.state != self.CANCELLED:
            self.state = self.ERROR
            self.error = error
        # Keep any resumable progress: the next attempt should resume, not
        # restart. Only release the transient handles.
        self._release_resources()

    def on_download_completed(self):
        if self.state == self.CANCELLED:
            return

        logger.debug("Finished downloading %s", self._log_name)
        if not self.downloaded_size:
            logger.warning("Downloaded file is empty")

        if not self.full_size:
            self.progress_fraction = 1.0
            self.progress_percentage = 100
        self.state = self.COMPLETED
        self._release_resources()
        # Download is complete — the resumable state is no longer needed.
        self._discard_persistent_state()

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


class SimpleDownloader(BaseDownloader):
    """Single-connection downloader: fetches the whole file in one stream."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.file_pointer = None

    def _prepare_destination(self) -> None:
        if self.overwrite and os.path.isfile(self.dest):
            os.remove(self.dest)
        self.file_pointer = open(self.dest, "wb")  # pylint: disable=consider-using-with

    def async_download(self) -> None:
        """Run the single-stream transfer with stall detection and retries.

        Retries up to RETRY_ATTEMPTS times on stalls and transient errors.
        Non-retryable errors (HTTP 4xx except 408/429) fail immediately.
        """
        last_error = None
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                self._do_download()
                self.on_download_completed()
                return  # Success
            except DownloadStallError as ex:
                last_error = ex
                if self.stop_request and self.stop_request.is_set():
                    break
                logger.warning(
                    "Download stall detected (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1,
                    self.RETRY_ATTEMPTS,
                    ex,
                    self.RETRY_DELAY,
                )
                time.sleep(self.RETRY_DELAY)
                self._prepare_retry()
            except requests.HTTPError as ex:
                last_error = ex
                if self._is_retryable_http_error(ex):
                    if self.stop_request and self.stop_request.is_set():
                        break
                    logger.warning(
                        "Transient HTTP error (attempt %d/%d): %s — retrying in %ds",
                        attempt + 1,
                        self.RETRY_ATTEMPTS,
                        ex,
                        self.RETRY_DELAY,
                    )
                    time.sleep(self.RETRY_DELAY)
                    self._prepare_retry()
                else:
                    # Non-retryable (4xx client errors like 404, 403)
                    logger.error("Non-retryable HTTP error: %s", ex)
                    self.on_download_failed(ex)
                    return
            except Exception as ex:
                last_error = ex
                if self.stop_request and self.stop_request.is_set():
                    break
                if attempt < self.RETRY_ATTEMPTS - 1:
                    logger.warning(
                        "Download error (attempt %d/%d): %s — retrying in %ds",
                        attempt + 1,
                        self.RETRY_ATTEMPTS,
                        ex,
                        self.RETRY_DELAY,
                    )
                    time.sleep(self.RETRY_DELAY)
                    self._prepare_retry()
                else:
                    logger.exception("Download failed after %d attempts: %s", self.RETRY_ATTEMPTS, ex)
                    self.on_download_failed(ex)
                    return

        # All retries exhausted
        if last_error:
            logger.error("Download failed after %d attempts: %s", self.RETRY_ATTEMPTS, last_error)
            self.on_download_failed(last_error)

    @staticmethod
    def _is_retryable_http_error(error: requests.HTTPError) -> bool:
        """Check if an HTTP error is transient and worth retrying.

        Retries on server errors (5xx), timeouts (408), and rate limits (429).
        Client errors like 404, 403 are not retried.
        """
        if error.response is None:
            return True  # No response means connection-level failure
        status = error.response.status_code
        return status >= 500 or status in (408, 429)

    def _do_download(self) -> None:
        """Perform a single download attempt with stall detection."""
        headers = requests.utils.default_headers()
        headers["User-Agent"] = "Lutris/%s" % __version__
        if self.referer:
            headers["Referer"] = self.referer
        if self.headers:
            for key, value in self.headers.items():
                headers[key] = value

        # Use provided session for connection pooling, or fall back to plain requests
        requester = self.session if self.session else requests
        response = requester.get(self.url, headers=headers, stream=True, timeout=30, cookies=self.cookies)
        if response.status_code != 200:
            logger.info("%s returned a %s error", self.url, response.status_code)
        response.raise_for_status()
        self.full_size = int(response.headers.get("Content-Length", "").strip() or 0)
        self.progress_event.set()

        # A fresh stall monitor per attempt — see StallMonitor.
        stall_monitor = self._new_stall_monitor()
        stream_bytes = 0

        for chunk in response.iter_content(chunk_size=self.chunk_size):
            if not self.file_pointer:
                break
            if self.stop_request and self.stop_request.is_set():
                break
            if chunk:
                stream_bytes += len(chunk)
                self.downloaded_size += len(chunk)
                self.file_pointer.write(chunk)
                stall_monitor.check(stream_bytes)
            self.progress_event.set()

    def _prepare_retry(self) -> None:
        """Restart the file from the beginning for a retry attempt."""
        self.downloaded_size = 0
        if self.file_pointer:
            self.file_pointer.close()
        self.file_pointer = open(self.dest, "wb")  # pylint: disable=consider-using-with

    def _release_resources(self) -> None:
        if self.file_pointer:
            self.file_pointer.close()
            self.file_pointer = None
