"""Downloads of files to a destination, with their progress kept as plain data.

These run the whole download: they create the downloaders, poll them on the main
loop, retry, move finished files into place and keep the download cache's
locks up to date. A frontend only displays `status` and `state`, follows
`changed`, and calls start(), cancel() and retry().
"""

import enum
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlparse

from lutris.util.download_cache import CacheState, create_cache_lock, update_cache_lock
from lutris.util.downloader import BaseDownloader, SimpleDownloader, TransferRateMeter
from lutris.util.jobs import COMPLETED_IDLE_TASK, IdleTask, schedule_repeating_at_idle
from lutris.util.log import logger
from lutris.util.notifications import NotificationSource

if TYPE_CHECKING:
    from lutris.installer.installer_file import InstallerFile
    from lutris.installer.installer_file_collection import InstallerFileCollection

# How often a running download checks its downloaders
POLL_INTERVAL_SECONDS = 0.5

# Maximum number of a collection's files downloading at the same time. Keeping
# this at 2 ("prefetch-one") eliminates the cold-start gap between files
# without overloading the CDN (GOGDownloader already opens 4 Range connections
# per file)
MAX_CONCURRENT_FILES = 2


class DownloadState(enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class DownloadStatus:
    """How far a download has got."""

    fraction: float = 0.0
    downloaded_size: int = 0
    full_size: int = 0
    # Bytes per second
    speed: float = 0.0
    # As "H:MM:SS", or "???" while it can't be estimated
    time_left: str = ""
    # Names of the files being downloaded right now (collections only)
    current_files: tuple[str, ...] = ()


class FileDownload(Protocol):
    """What FileDownload and FileCollectionDownload have in common."""

    title: str
    state: DownloadState
    status: DownloadStatus
    error: BaseException | None
    changed: NotificationSource

    def start(self) -> None: ...

    def cancel(self) -> None: ...

    def retry(self) -> None: ...


class SingleFileDownload:
    """Downloads one URL to a destination file, by way of a temporary file.

    `changed` fires whenever `state` or `status` changes, with a snapshot of
    `(state, status, error)`; handlers should use that, as by the time they run
    the download may have moved on. `error` is set when the download failed, and
    also when it couldn't even start, in which case it ends up CANCELLED rather
    than FAILED.
    """

    def __init__(
        self,
        url: str,
        dest: str,
        temp: str | None = None,
        referer: str | None = None,
        title: str | None = None,
        downloader: BaseDownloader | None = None,
    ) -> None:
        self.url = url
        self.dest = dest
        self.temp = temp or (dest + ".tmp")
        self.referer = referer
        if not title:
            parsed_url = urlparse(url)
            title = "%s%s" % (parsed_url.netloc, parsed_url.path)
        self.title = title
        self.state = DownloadState.PENDING
        self.status = DownloadStatus()
        self.error: BaseException | None = None
        self.changed = NotificationSource()
        self._downloader = downloader
        self._poll_task: IdleTask = COMPLETED_IDLE_TASK

        if os.path.exists(self.temp):
            os.remove(self.temp)

    @property
    def downloader(self) -> BaseDownloader:
        if not self._downloader:
            self._downloader = SimpleDownloader(self.url, self.temp, referer=self.referer, overwrite=True)
        return self._downloader

    def start(self) -> None:
        self.error = None
        try:
            downloader = self.downloader
        except RuntimeError as ex:
            self.error = ex
            self._set_state(DownloadState.CANCELLED)
            return

        create_cache_lock(self.dest, CacheState.DOWNLOADING)
        self._set_state(DownloadState.DOWNLOADING)
        self._poll_task.unschedule()
        self._poll_task = schedule_repeating_at_idle(self._poll, interval_seconds=POLL_INTERVAL_SECONDS)
        if downloader.state != downloader.DOWNLOADING:
            downloader.start()

    def cancel(self) -> None:
        if self._downloader:
            self._downloader.cancel()
        if self.state in (DownloadState.PENDING, DownloadState.DOWNLOADING):
            self._set_state(DownloadState.CANCELLED)

    def retry(self) -> None:
        self.downloader.reset()
        self.start()

    def _poll(self) -> bool:
        if self.state != DownloadState.DOWNLOADING:
            return False

        downloader = self.downloader
        fraction = min(downloader.check_progress(), 1)
        if downloader.state == downloader.CANCELLED:
            self.status = DownloadStatus()
            self._set_state(DownloadState.CANCELLED)
            return False
        if downloader.state == downloader.ERROR:
            self.status = DownloadStatus()
            self.error = downloader.error
            self._set_state(DownloadState.FAILED)
            return False

        self.status = DownloadStatus(
            fraction=fraction,
            downloaded_size=downloader.downloaded_size,
            full_size=downloader.full_size,
            speed=float(downloader.average_speed),
            time_left=downloader.time_left,
        )
        if downloader.state == downloader.COMPLETED:
            os.rename(self.temp, self.dest)
            update_cache_lock(self.dest, CacheState.DOWNLOADED)
            self._set_state(DownloadState.COMPLETED)
            return False

        self._notify()
        return True

    def _set_state(self, state: DownloadState) -> None:
        self.state = state
        self._notify()

    def _notify(self) -> None:
        self.changed.fire(self.state, self.status, self.error)


def _temp_path(file: "InstallerFile") -> str:
    """Where a collection's file is downloaded to before being moved into place."""
    return file.dest_file + ".tmp"


class _ActiveDownload:
    """One of a collection's files that is downloading, and its retries."""

    __slots__ = ("downloader", "file", "num_retries")

    def __init__(self, file: "InstallerFile", downloader: BaseDownloader) -> None:
        self.file = file
        self.downloader = downloader
        self.num_retries = 0


class FileCollectionDownload:
    """Downloads the files of an InstallerFileCollection, a couple at a time.

    Files already at their destination are skipped. A file that fails is retried
    up to `max_retries` times on its own; after that the whole collection fails.
    `changed` and `error` work as for SingleFileDownload.
    """

    max_retries = 3

    def __init__(self, file_collection: "InstallerFileCollection") -> None:
        self.title = file_collection.human_url
        self.full_size = file_collection.full_size
        self.num_files_to_download = file_collection.num_files
        self.num_files_downloaded = 0
        self.state = DownloadState.PENDING
        self.status = DownloadStatus(full_size=self.full_size)
        self.error: BaseException | None = None
        self.changed = NotificationSource()

        self._file_queue: list[InstallerFile] = file_collection.files_list.copy()
        self._active_downloads: list[_ActiveDownload] = []
        # Bytes of each file that has finished, by destination
        self._completed_sizes: dict[str, int] = {}
        self.speed_meter = TransferRateMeter()
        self._avg_speed = 0.0
        self._time_left = "00:00:00"
        self._time_left_check_time = 0.0
        self._poll_task: IdleTask = COMPLETED_IDLE_TASK

    def start(self) -> None:
        """Start downloading, up to MAX_CONCURRENT_FILES files at once."""
        self.error = None
        file = self._pop_next_downloadable_file()
        if file is None:
            self._set_state(DownloadState.COMPLETED)
            return

        if not self._start_one(file):
            return  # The error is already reported

        self._set_state(DownloadState.DOWNLOADING)
        self._poll_task.unschedule()
        self._poll_task = schedule_repeating_at_idle(self._poll, interval_seconds=POLL_INTERVAL_SECONDS)
        self._start_prefetch()

    def cancel(self) -> None:
        """Cancel every file still downloading."""
        logger.debug("Download cancel requested")
        self._stop_all()
        if self.state in (DownloadState.PENDING, DownloadState.DOWNLOADING):
            self._set_state(DownloadState.CANCELLED)

    def retry(self) -> None:
        """Start again, after a cancellation or failure, with the files not yet done."""
        logger.debug("Retrying download")
        self._stop_all()
        self.start()

    def _create_downloader(self, file: "InstallerFile") -> BaseDownloader | None:
        """Create a downloader for `file`, or record the error and return None."""
        tmp_path = _temp_path(file)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        try:
            downloader_cls = getattr(file, "downloader_class", None) or SimpleDownloader
            downloader = downloader_cls(file.url, tmp_path, referer=file.referer, overwrite=True)
        except RuntimeError as ex:
            self.error = ex
            return None

        create_cache_lock(file.dest_file, CacheState.DOWNLOADING)
        return downloader

    def _pop_next_downloadable_file(self) -> "InstallerFile | None":
        """Pop the next file to download, skipping those already at their destination."""
        while self._file_queue:
            file = self._file_queue.pop()
            if os.path.exists(file.dest_file):
                logger.info("File exists, skipping download: '%s'", file.dest_file)
                self.num_files_downloaded += 1
                self._completed_sizes[file.dest_file] = os.path.getsize(file.dest_file)
                continue
            return file
        return None

    def _start_one(self, file: "InstallerFile") -> bool:
        """Start downloading `file`; on failure, cancel the collection and return False."""
        downloader = self._create_downloader(file)
        if downloader is None:
            self._file_queue.append(file)
            self._stop_all()
            self._set_state(DownloadState.CANCELLED)
            return False
        self._active_downloads.append(_ActiveDownload(file, downloader))
        downloader.start()
        return True

    def _start_prefetch(self) -> None:
        """If there is room and files remain, start the next download."""
        if len(self._active_downloads) >= MAX_CONCURRENT_FILES:
            return
        file = self._pop_next_downloadable_file()
        if file is not None:
            self._start_one(file)

    def _stop_all(self) -> None:
        """Cancel the active downloads, putting their files back in the queue."""
        for active in self._active_downloads:
            active.downloader.cancel()
            self._file_queue.append(active.file)
        self._active_downloads.clear()

    def _aggregate_downloaded_size(self) -> int:
        """Bytes downloaded so far, of finished and active files."""
        completed = sum(self._completed_sizes.values())
        active = sum(active.downloader.downloaded_size for active in self._active_downloads)
        return completed + active

    def _poll(self) -> bool:
        """Check the active downloads, retry or finish them, and update the status."""
        if self.state != DownloadState.DOWNLOADING or not self._active_downloads:
            return False

        finished = []
        for active in self._active_downloads:
            downloader = active.downloader
            if downloader.state == downloader.CANCELLED:
                self._stop_all()
                self.status = DownloadStatus(full_size=self.full_size)
                self._set_state(DownloadState.CANCELLED)
                return False

            if downloader.state == downloader.ERROR:
                if active.num_retries >= self.max_retries:
                    self.error = downloader.error
                    self._stop_all()
                    self._set_state(DownloadState.FAILED)
                    return False
                active.num_retries += 1
                logger.debug(
                    "Retrying file %s (attempt %d/%d)", active.file.filename, active.num_retries, self.max_retries
                )
                downloader.reset()
                new_downloader = self._create_downloader(active.file)
                if new_downloader is None:
                    self._stop_all()
                    self._set_state(DownloadState.CANCELLED)
                    return False
                active.downloader = new_downloader
                new_downloader.start()
                continue

            if downloader.state == downloader.COMPLETED:
                finished.append(active)

        for active in finished:
            self.num_files_downloaded += 1
            self._completed_sizes[active.file.dest_file] = active.downloader.downloaded_size
            os.rename(_temp_path(active.file), active.file.dest_file)
            update_cache_lock(active.file.dest_file, CacheState.DOWNLOADED)
            self._active_downloads.remove(active)

        if finished:
            self._start_prefetch()

        downloaded_size = self._aggregate_downloaded_size()
        self._update_speed_and_time(downloaded_size)
        self.status = DownloadStatus(
            fraction=min(downloaded_size / self.full_size, 1) if self.full_size > 0 else 0.0,
            downloaded_size=downloaded_size,
            full_size=self.full_size,
            speed=self._avg_speed,
            time_left=self._time_left,
            current_files=tuple(active.file.filename for active in self._active_downloads),
        )

        if not self._active_downloads and not self._file_queue:
            self._set_state(DownloadState.COMPLETED)
            return False

        self._notify()
        return True

    def _update_speed_and_time(self, downloaded_size: int) -> None:
        """Update the average speed and time left, at most once a second."""
        self.speed_meter.add_sample(downloaded_size)
        now = time.monotonic()
        if now - self._time_left_check_time < 1:
            return
        self._time_left_check_time = now

        self._avg_speed = self.speed_meter.rate
        if self._avg_speed == 0:
            self._time_left = "???"
            return

        minutes, seconds = divmod((self.full_size - downloaded_size) / self._avg_speed, 60)
        hours, minutes = divmod(minutes, 60)
        self._time_left = "%d:%02d:%02d" % (hours, minutes, seconds)

    def _set_state(self, state: DownloadState) -> None:
        self.state = state
        self._notify()

    def _notify(self) -> None:
        self.changed.fire(self.state, self.status, self.error)
