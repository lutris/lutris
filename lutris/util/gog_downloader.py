"""Multi-connection parallel downloader for GOG game files.

Uses HTTP Range requests to download different byte ranges of a file
simultaneously across multiple threads, significantly improving download
speeds for large GOG installer files.

This downloader is a drop-in replacement for the standard Downloader class,
maintaining API compatibility with DownloadProgressBox and
DownloadCollectionProgressBox.
"""

import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

from lutris import __version__
from lutris.util import jobs
from lutris.util.download_progress import DownloadProgress
from lutris.util.downloader import DEFAULT_CHUNK_SIZE, Downloader, get_time
from lutris.util.log import logger


class GOGDownloader(Downloader):
    """Multi-connection parallel downloader optimized for GOG CDN downloads.

    Downloads large files using multiple simultaneous HTTP Range requests,
    each writing to a different region of the output file. Falls back to
    single-stream download if the server doesn't support Range requests
    or the file is too small to benefit from parallelism.

    Designed to be API-compatible with Downloader so it works seamlessly
    with DownloadProgressBox and DownloadCollectionProgressBox.
    """

    DEFAULT_WORKERS = 4
    MIN_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB minimum per worker
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds between retries

    def __init__(
        self,
        url: str,
        dest: str,
        overwrite: bool = False,
        referer: Optional[str] = None,
        cookies: Any = None,
        headers: Dict[str, str] = None,
        session: Optional[requests.Session] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        num_workers: int = DEFAULT_WORKERS,
    ) -> None:
        super().__init__(
            url=url,
            dest=dest,
            overwrite=overwrite,
            referer=referer,
            cookies=cookies,
            headers=headers,
            session=session,
            chunk_size=chunk_size,
        )
        self.num_workers = max(1, num_workers)
        self._download_lock = threading.Lock()
        self._progress: Optional[DownloadProgress] = None
        # Pipelining: bounded queue decouples download I/O from disk writes
        self._write_queue: queue.Queue = queue.Queue(maxsize=64)
        self._writer_error: Optional[Exception] = None
        self._writer_error_event = threading.Event()
        # Create a dedicated session with connection pooling sized for our workers
        self._parallel_session = requests.Session()
        adapter = HTTPAdapter(pool_maxsize=self.num_workers + 2)
        self._parallel_session.mount("https://", adapter)
        self._parallel_session.mount("http://", adapter)
        self._parallel_session.headers["User-Agent"] = "Lutris/%s" % __version__

    def __repr__(self):
        return "GOG parallel downloader (%d workers) for %s" % (self.num_workers, self.url)

    def start(self):
        """Start parallel download job.

        If a previous download was interrupted (hibernate, crash, network
        error), the progress file and partial destination file are detected
        and the download resumes from the last completed byte ranges
        instead of starting over.
        """
        logger.debug("⬇ GOG parallel (%d workers): %s", self.num_workers, self.url)
        self.state = self.DOWNLOADING
        self.last_check_time = get_time()

        # Check for resumable progress before deleting anything
        can_resume = False
        if os.path.isfile(self.dest):
            progress = DownloadProgress(self.dest)
            if progress.load() and progress.get_remaining_ranges():
                can_resume = True
                logger.info(
                    "GOG download: found resumable progress for %s "
                    "(%d/%d ranges complete, %d bytes already downloaded)",
                    os.path.basename(self.dest),
                    len(progress.completed_ranges),
                    len(progress.total_ranges),
                    progress.get_completed_size(),
                )

        if not can_resume and self.overwrite and os.path.isfile(self.dest):
            os.remove(self.dest)
            # Also clean stale progress files
            progress_path = DownloadProgress.progress_path_for(self.dest)
            if os.path.isfile(progress_path):
                os.remove(progress_path)

        # Workers manage their own file I/O - no shared file_pointer needed
        self.file_pointer = None
        self.thread = jobs.AsyncCall(self.async_download, None)
        self.stop_request = self.thread.stop_request

    def cancel(self):
        """Request download stop and remove destination file.

        Explicit user cancellation removes both the partial file and
        the progress file so the next attempt starts fresh.
        """
        logger.debug("❌ GOG parallel: %s", self.url)
        self.state = self.CANCELLED
        if self.stop_request:
            self.stop_request.set()
        # No shared file_pointer to close - workers handle their own
        if os.path.isfile(self.dest):
            os.remove(self.dest)
        # Clean up progress file on explicit cancel
        if self._progress:
            self._progress.cleanup()
            self._progress = None

    def on_download_completed(self):
        """Mark download as complete and clean up progress file."""
        if self.state == self.CANCELLED:
            return
        logger.debug("✅ GOG parallel download finished: %s", self.url)
        if not self.downloaded_size:
            logger.warning("Downloaded file is empty")
        if not self.full_size:
            self.progress_fraction = 1.0
            self.progress_percentage = 100
        self.state = self.COMPLETED
        # No shared file_pointer to close
        # Remove progress file — download is complete
        if self._progress:
            self._progress.cleanup()
            self._progress = None

    def _build_request_headers(self) -> Dict[str, str]:
        """Build HTTP headers for download requests."""
        headers: Dict[str, str] = dict(requests.utils.default_headers())
        headers["User-Agent"] = "Lutris/%s" % __version__
        if self.referer:
            headers["Referer"] = self.referer
        if self.headers:
            headers.update(self.headers)
        return headers

    def _calculate_ranges(self, file_size: int) -> List[Tuple[int, int]]:
        """Split file into byte ranges for parallel download.

        Returns a list of (start, end) tuples representing inclusive byte ranges.
        """
        chunk_size = file_size // self.num_workers
        ranges = []
        for i in range(self.num_workers):
            start = i * chunk_size
            end = file_size - 1 if i == self.num_workers - 1 else (i + 1) * chunk_size - 1
            ranges.append((start, end))
        return ranges

    def _writer_loop(self) -> None:
        """Dedicated writer thread: dequeues chunks and writes to disk.

        Consumes (offset, data, range_start, range_end) tuples from the
        write queue. A None sentinel signals the writer to exit.

        All disk I/O and progress tracking happens here, keeping download
        workers free from disk latency.
        """
        try:
            with open(self.dest, "r+b") as f:
                while True:
                    if self.stop_request and self.stop_request.is_set():
                        # Drain remaining items on cancel
                        break
                    try:
                        item = self._write_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if item is None:
                        # Sentinel — all downloads complete
                        break

                    offset, data, range_start, range_end = item
                    f.seek(offset)
                    f.write(data)
                    with self._download_lock:
                        self.downloaded_size += len(data)
                    self.progress_event.set()

                    # If this write completes a range, mark it in progress file
                    if range_end is not None and offset + len(data) >= range_end + 1:
                        if self._progress:
                            self._progress.mark_range_complete(range_start, range_end)
        except Exception as ex:
            logger.error("Writer thread failed: %s", ex)
            self._writer_error = ex
            self._writer_error_event.set()

    def async_download(self):
        """Execute multi-connection parallel download with resume support.

        On each invocation the method:
        1. Probes the server for the final URL, file size, and Range support.
        2. Checks for an existing ``.progress`` file alongside the
           destination.  If one is found and the file size matches, the
           download resumes from only the remaining byte ranges.
        3. Pre-allocates (or reuses) the destination file and launches
           parallel workers for the outstanding ranges.
        4. On success the progress file is removed.  On failure or
           interruption (hibernate, crash) the progress file and partial
           destination are preserved for the next attempt.
        """
        try:
            headers = self._build_request_headers()

            # Step 1: Resolve URL (follow redirects) and check capabilities
            final_url, file_size, supports_range = self._probe_server(headers)
            self.full_size = file_size

            # Fall back to single-stream if Range not supported or file too small
            if not supports_range or file_size < self.MIN_CHUNK_SIZE * 2:
                logger.info(
                    "GOG download: falling back to single-stream (range=%s, size=%d bytes)",
                    supports_range,
                    file_size,
                )
                self._single_stream_download(final_url, headers)
                return

            self.progress_event.set()  # Signal that size is known

            # Step 2: Check for resumable progress
            self._progress = DownloadProgress(self.dest)
            ranges_to_download = None

            if self._progress.load() and self._progress.is_compatible(file_size):
                remaining = self._progress.get_remaining_ranges()
                if remaining:
                    already_done = self._progress.get_completed_size()
                    logger.info(
                        "GOG download: resuming — %d/%d ranges done, %d bytes already on disk, %d bytes remaining",
                        len(self._progress.completed_ranges),
                        len(self._progress.total_ranges),
                        already_done,
                        file_size - already_done,
                    )
                    # Credit previously-downloaded bytes to progress tracking
                    with self._download_lock:
                        self.downloaded_size = already_done
                    ranges_to_download = remaining
                else:
                    # All ranges already complete — verify file exists & size
                    if os.path.isfile(self.dest) and os.path.getsize(self.dest) == file_size:
                        logger.info(
                            "GOG download: all ranges already complete, skipping download of %s",
                            os.path.basename(self.dest),
                        )
                        with self._download_lock:
                            self.downloaded_size = file_size
                        self.on_download_completed()
                        return

            # Step 3: Compute ranges (fresh or from progress)
            if ranges_to_download is None:
                # Fresh download — pre-allocate output file
                with open(self.dest, "wb") as f:
                    f.truncate(file_size)
                all_ranges = self._calculate_ranges(file_size)
                self._progress.create(final_url, file_size, all_ranges)
                ranges_to_download = all_ranges
            else:
                # Resuming — verify dest file exists and has correct size
                if not os.path.isfile(self.dest) or os.path.getsize(self.dest) != file_size:
                    logger.warning("GOG download: dest file missing or wrong size during resume, starting fresh")
                    with open(self.dest, "wb") as f:
                        f.truncate(file_size)
                    all_ranges = self._calculate_ranges(file_size)
                    self._progress.create(final_url, file_size, all_ranges)
                    ranges_to_download = all_ranges
                    with self._download_lock:
                        self.downloaded_size = 0

            total_remaining = sum(e - s + 1 for s, e in ranges_to_download)
            logger.info(
                "GOG parallel download: %d workers, %d ranges to download, %d MB remaining of %d MB total",
                self.num_workers,
                len(ranges_to_download),
                total_remaining // (1024 * 1024),
                file_size // (1024 * 1024),
            )

            # Step 4: Download chunks in parallel with pipelined writes
            # Reset writer error state
            self._writer_error = None
            self._writer_error_event.clear()

            # Start dedicated writer thread
            writer_thread = threading.Thread(target=self._writer_loop, name="GOGDownloader-writer", daemon=True)
            writer_thread.start()

            errors = []
            try:
                with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                    future_to_range = {}
                    for start, end in ranges_to_download:
                        future = executor.submit(self._download_range, final_url, headers, start, end)
                        future_to_range[future] = (start, end)

                    for future in as_completed(future_to_range):
                        try:
                            future.result()
                        except Exception as ex:
                            rng = future_to_range[future]
                            logger.error("Worker failed for range %d-%d: %s", rng[0], rng[1], ex)
                            errors.append(ex)
                            # Signal other workers to stop
                            if self.stop_request:
                                self.stop_request.set()
            finally:
                # Signal writer thread to exit and wait for it
                self._write_queue.put(None)
                writer_thread.join(timeout=30)

            # Check for writer errors
            if self._writer_error:
                raise self._writer_error

            if errors:
                raise errors[0]

            self.on_download_completed()
        except Exception as ex:
            logger.exception("GOG parallel download failed: %s", ex)
            self.on_download_failed(ex)

    def _probe_server(self, headers: dict) -> Tuple[str, int, bool]:
        """Probe the server to determine final URL, file size, and Range support.

        Uses a HEAD request to follow redirects (e.g., GOG API → CDN URL),
        get Content-Length, and check Accept-Ranges header.

        Returns:
            Tuple of (final_url, file_size, supports_range)
        """
        resp = self._parallel_session.head(
            self.url, headers=headers, allow_redirects=True, timeout=30, cookies=self.cookies
        )
        resp.raise_for_status()

        final_url = resp.url
        file_size = int(resp.headers.get("Content-Length", 0))
        accept_ranges = resp.headers.get("Accept-Ranges", "")
        supports_range = "bytes" in accept_ranges.lower()

        # Some servers don't advertise Accept-Ranges but still support it.
        # If we got a Content-Length, try a small Range request to verify.
        if file_size and not supports_range:
            supports_range = self._test_range_support(final_url, headers)

        logger.debug(
            "GOG probe: url=%s, size=%d, range=%s",
            final_url[:80],
            file_size,
            supports_range,
        )
        return final_url, file_size, supports_range

    def _test_range_support(self, url: str, headers: dict) -> bool:
        """Test if server actually supports Range requests with a small probe."""
        try:
            test_headers = dict(headers)
            test_headers["Range"] = "bytes=0-0"
            resp = self._parallel_session.get(url, headers=test_headers, stream=True, timeout=10, cookies=self.cookies)
            resp.close()
            return resp.status_code == 206
        except Exception:
            return False

    def _download_range(self, url: str, headers: dict, start: int, end: int) -> None:
        """Download a specific byte range and enqueue data for the writer thread.

        Each worker downloads its assigned byte range and puts chunks into
        the write queue for the dedicated writer thread. Workers never
        perform file I/O directly, keeping them free from disk latency.

        Retries up to RETRY_ATTEMPTS times with exponential backoff.
        """
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                range_headers = dict(headers)
                range_headers["Range"] = "bytes=%d-%d" % (start, end)

                response = self._parallel_session.get(
                    url,
                    headers=range_headers,
                    stream=True,
                    timeout=30,
                    cookies=self.cookies,
                )

                if response.status_code not in (200, 206):
                    raise requests.HTTPError(
                        "HTTP %d for range %d-%d" % (response.status_code, start, end),
                        response=response,
                    )

                # If server returned 200 (ignoring Range), only write our portion
                if response.status_code == 200:
                    logger.warning(
                        "Server ignored Range header, reading full response for range %d-%d",
                        start,
                        end,
                    )
                    self._write_from_full_response(response, start, end)
                    return

                # Normal 206 Partial Content response — enqueue for writer
                self._reset_stall_state()
                stream_bytes = 0
                current_offset = start
                range_size = end - start + 1

                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if self.stop_request and self.stop_request.is_set():
                        return
                    if self._writer_error_event.is_set():
                        return  # Writer failed, stop downloading
                    if chunk:
                        stream_bytes += len(chunk)
                        # Mark the last chunk of this range so writer knows when to
                        # record the range as complete
                        is_last_chunk = stream_bytes >= range_size
                        range_end_marker = end if is_last_chunk else None
                        self._write_queue.put((current_offset, chunk, start, range_end_marker))
                        current_offset += len(chunk)
                        self._check_stall(stream_bytes)

                return  # Success

            except Exception as ex:
                if self.stop_request and self.stop_request.is_set():
                    return  # Cancelled, don't retry
                if attempt < self.RETRY_ATTEMPTS - 1:
                    wait = self.RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        "GOG range %d-%d attempt %d/%d failed: %s, retrying in %ds...",
                        start,
                        end,
                        attempt + 1,
                        self.RETRY_ATTEMPTS,
                        ex,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    raise

    def _write_from_full_response(self, response: requests.Response, start: int, end: int) -> None:
        """Handle the case where server returns 200 instead of 206.

        Read the full response but only enqueue our byte range portion.
        This is a fallback for non-compliant servers.
        """
        bytes_read = 0
        current_offset = start
        range_size = end - start + 1
        enqueued_bytes = 0

        for chunk in response.iter_content(chunk_size=self.chunk_size):
            if self.stop_request and self.stop_request.is_set():
                return
            if self._writer_error_event.is_set():
                return
            if not chunk:
                continue

            # Only write the portion that falls within our range
            chunk_start = bytes_read
            chunk_end = bytes_read + len(chunk)

            if chunk_end <= start:
                # Before our range, skip
                bytes_read += len(chunk)
                continue
            elif chunk_start >= end + 1:
                # Past our range, done
                break
            else:
                # Calculate the slice of this chunk we need
                slice_start = max(0, start - chunk_start)
                slice_end = min(len(chunk), end + 1 - chunk_start)
                data = chunk[slice_start:slice_end]
                enqueued_bytes += len(data)
                is_last = enqueued_bytes >= range_size
                self._write_queue.put((current_offset, data, start, end if is_last else None))
                current_offset += len(data)

            bytes_read += len(chunk)
            if bytes_read >= end + 1:
                break

    def _single_stream_download(self, url: str, headers: dict) -> None:
        """Fallback single-stream download when Range requests aren't supported.

        Uses the parallel session for connection pooling benefits.
        """
        response = self._parallel_session.get(url, headers=headers, stream=True, timeout=30, cookies=self.cookies)
        response.raise_for_status()
        self.full_size = int(response.headers.get("Content-Length", "").strip() or 0)
        self.progress_event.set()

        with open(self.dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if self.stop_request and self.stop_request.is_set():
                    break
                if chunk:
                    self.downloaded_size += len(chunk)
                    f.write(chunk)
                self.progress_event.set()

        self.on_download_completed()
