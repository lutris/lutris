import os
import time
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import GObject, Gtk, Pango

from lutris.gui.dialogs import display_error
from lutris.util.download_cache import CacheState, create_cache_lock, update_cache_lock
from lutris.util.downloader import Downloader
from lutris.util.jobs import schedule_repeating_at_idle
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size

if TYPE_CHECKING:
    from lutris.installer.installer_file_collection import InstallerFileCollection

# Same reason as Downloader
get_time = time.monotonic

# Maximum number of file downloads running at the same time.  Keeping
# this at 2 ("prefetch-one") eliminates the cold-start gap between
# files without overloading the CDN (GOGDownloader already opens 4
# Range connections per file).
MAX_CONCURRENT_FILES = 2


class _ActiveDownload:
    """Tracks one active file download and its retry state."""

    __slots__ = ("downloader", "file", "num_retries")

    def __init__(self, file, downloader) -> None:
        self.file = file
        self.downloader = downloader
        self.num_retries = 0


class DownloadCollectionProgressBox(Gtk.Box):
    """Progress bar used to monitor a collection of files download."""

    max_retries = 3

    __gsignals__ = {
        "complete": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(
        self,
        file_collection: "InstallerFileCollection",
        cancelable: bool = True,
        downloader: Downloader | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.downloader = downloader
        self.is_complete = False
        self._file_queue = file_collection.files_list.copy()
        self.title = file_collection.human_url
        self.num_files_downloaded = 0
        self.num_files_to_download = file_collection.num_files
        self.full_size = file_collection.full_size
        self.time_left = "00:00:00"
        self.time_left_check_time = 0
        self.last_size = 0
        self.avg_speed = 0
        self.speed_list = []

        # --- Concurrent download state ---
        # List of _ActiveDownload objects currently downloading.
        self._active_downloads: list[_ActiveDownload] = []
        # Cumulative bytes for files that have already completed.
        self._completed_sizes: dict[str, int] = {}

        # Legacy compat: kept for the single-downloader callers that
        # pass a ``downloader`` kwarg (e.g. on_retry_clicked).
        self.num_retries = 0

        top_box = Gtk.Box()
        self.main_label = Gtk.Label(label=self.title)
        self.main_label.set_xalign(0)
        self.main_label.set_wrap(True)
        self.main_label.set_margin_bottom(10)
        self.main_label.set_selectable(True)
        self.main_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        top_box.append(self.main_label)

        self.cancel_button = Gtk.Button.new_with_mnemonic(_("_Cancel"))
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_cancel_clicked)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        self.cancel_button.set_hexpand(True)
        self.cancel_button.set_halign(Gtk.Align.END)
        top_box.append(self.cancel_button)

        self.append(top_box)

        self.file_name_label = Gtk.Label()
        self.file_name_label.set_xalign(0)
        self.file_name_label.set_wrap(True)
        self.file_name_label.set_margin_bottom(10)
        self.file_name_label.set_selectable(True)
        self.file_name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.append(self.file_name_label)

        progress_box = Gtk.Box()
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(5)
        self.progressbar.set_margin_bottom(5)
        self.progressbar.set_margin_end(10)
        self.progressbar.set_hexpand(True)
        progress_box.append(self.progressbar)

        self.append(progress_box)

        self.progress_label = Gtk.Label()
        self.progress_label.set_xalign(0)
        self.append(self.progress_label)

        self.cancel_button.set_visible(False)

    # ------------------------------------------------------------------
    # Downloader creation helper
    # ------------------------------------------------------------------

    def _create_downloader(self, file):
        """Create a Downloader (or subclass) for *file* and return it.

        Handles `downloader_class` look-up, ``.tmp`` path creation and
        cache-lock creation.  Returns ``None`` on failure.
        """
        tmp_path = file.dest_file + ".tmp"
        file.tmp_file = tmp_path
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        try:
            downloader_cls = getattr(file, "downloader_class", None) or Downloader
            dl = downloader_cls(file.url, file.tmp_file, referer=file.referer, overwrite=True)
        except RuntimeError as ex:
            display_error(ex, parent=self.get_root())
            return None

        create_cache_lock(file.dest_file, CacheState.DOWNLOADING)
        return dl

    # ------------------------------------------------------------------
    # File-label helpers
    # ------------------------------------------------------------------

    def _update_active_file_labels(self):
        """Set the file-name label to the names of all active downloads."""
        names = [ad.file.filename for ad in self._active_downloads]
        self.file_name_label.set_text(", ".join(names) if names else "")

    # ------------------------------------------------------------------
    # Queue helpers
    # ------------------------------------------------------------------

    def _pop_next_downloadable_file(self):
        """Pop and return the next file from the queue, skipping cached files.

        Returns ``None`` when the queue is empty.
        """
        while self._file_queue:
            file = self._file_queue.pop()
            if os.path.exists(file.dest_file):
                logger.info("File exists, skipping download: '%s'", file.dest_file)
                self.num_files_downloaded += 1
                size = os.path.getsize(file.dest_file)
                self._completed_sizes[file.dest_file] = size
                continue
            return file
        return None

    # ------------------------------------------------------------------
    # Start / prefetch
    # ------------------------------------------------------------------

    def _start_one(self, file):
        """Create a downloader for *file*, add to active list, and start it.

        Returns the ``_ActiveDownload`` on success, ``None`` on failure.
        """
        dl = self._create_downloader(file)
        if dl is None:
            self.emit("cancel")
            return None
        ad = _ActiveDownload(file, dl)
        self._active_downloads.append(ad)
        dl.start()
        return ad

    def _start_prefetch(self):
        """If there is room and files remain, start the next download."""
        if len(self._active_downloads) >= MAX_CONCURRENT_FILES:
            return
        file = self._pop_next_downloadable_file()
        if file is None:
            return
        self._start_one(file)
        self._update_active_file_labels()

    def start(self) -> None:
        """Start downloading files from the collection.

        Launches up to ``MAX_CONCURRENT_FILES`` downloads immediately.
        """
        # If an external caller already supplied a downloader
        # (e.g. on_retry_clicked), honour it as the primary.
        if self.downloader:
            file = self._file_queue.pop() if self._file_queue else None
            if file is None:
                self.cancel_button.set_sensitive(False)
                self.is_complete = True
                self.emit("complete", {})
                return
            file.tmp_file = self.downloader.dest
            ad = _ActiveDownload(file, self.downloader)
            self._active_downloads.append(ad)
            self._update_active_file_labels()
            create_cache_lock(file.dest_file, CacheState.DOWNLOADING)
            schedule_repeating_at_idle(self._progress, interval_seconds=0.5)
            self.cancel_button.set_visible(True)
            self.cancel_button.set_sensitive(True)
            if self.downloader.state != self.downloader.DOWNLOADING:
                self.downloader.start()
            self._start_prefetch()
            return

        # Normal path: start first file, then prefetch
        file = self._pop_next_downloadable_file()
        if file is None:
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.emit("complete", {})
            return

        ad = self._start_one(file)
        if ad is None:
            return  # error already emitted

        self._update_active_file_labels()
        schedule_repeating_at_idle(self._progress, interval_seconds=0.5)
        self.cancel_button.set_visible(True)
        self.cancel_button.set_sensitive(True)

        # Prefetch the next file immediately
        self._start_prefetch()

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    def set_retry_button(self):
        """Transform the cancel button into a retry button"""
        self.cancel_button.set_label(_("Retry"))
        self.cancel_button.disconnect(self.cancel_cb_id)
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_retry_clicked)
        self.cancel_button.set_sensitive(True)

    def on_retry_clicked(self, button):
        """Retry current download."""
        logger.debug("Retrying download")
        button.set_label(_("Cancel"))
        button.disconnect(self.cancel_cb_id)
        self.cancel_cb_id = button.connect("clicked", self.on_cancel_clicked)
        if self.downloader:
            self.downloader.reset()
        self._active_downloads.clear()
        self.start()

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def on_cancel_clicked(self, _widget=None):
        """Cancel all active downloads."""
        logger.debug("Download cancel requested")
        for ad in self._active_downloads:
            ad.downloader.cancel()
        self._active_downloads.clear()
        self.downloader = None
        self.cancel_button.set_sensitive(False)
        self.emit("cancel")

    # ------------------------------------------------------------------
    # Aggregate progress helpers
    # ------------------------------------------------------------------

    def _aggregate_downloaded_size(self):
        """Return total bytes downloaded (completed + active)."""
        completed = sum(self._completed_sizes.values())
        active = sum(ad.downloader.downloaded_size for ad in self._active_downloads)
        return completed + active

    # ------------------------------------------------------------------
    # Progress polling
    # ------------------------------------------------------------------

    def _progress(self) -> bool:
        """Periodic callback: check active downloads, update UI."""
        if not self._active_downloads:
            return False  # nothing to poll

        # ---- Handle error / cancelled states on each active download ----
        finished = []
        for ad in self._active_downloads:
            state = ad.downloader.state
            if state == ad.downloader.CANCELLED:
                self.progressbar.set_fraction(0)
                self._set_text(_("Download interrupted"))
                self._cancel_all()
                self.emit("cancel")
                return False

            if state == ad.downloader.ERROR:
                if ad.num_retries >= self.max_retries:
                    # Exhausted retries — fail entire collection
                    self._set_text(str(ad.downloader.error)[:80])
                    self._cancel_all()
                    self.emit("error", ad.downloader.error)
                    return False
                # Retry this one download independently
                ad.num_retries += 1
                logger.debug(
                    "Retrying file %s (attempt %d/%d)",
                    ad.file.filename,
                    ad.num_retries,
                    self.max_retries,
                )
                ad.downloader.reset()
                ad.downloader = self._create_downloader(ad.file)
                if ad.downloader is None:
                    self._cancel_all()
                    self.emit("cancel")
                    return False
                ad.downloader.start()
                continue

            if state == ad.downloader.COMPLETED:
                finished.append(ad)

        # ---- Process completions ----
        for ad in finished:
            self.num_files_downloaded += 1
            self._completed_sizes[ad.file.dest_file] = ad.downloader.downloaded_size
            os.rename(ad.file.tmp_file, ad.file.dest_file)
            update_cache_lock(ad.file.dest_file, CacheState.DOWNLOADED)
            self._active_downloads.remove(ad)

        # If files finished, maybe start more prefetch downloads
        if finished:
            self._start_prefetch()
            self._update_active_file_labels()

        # ---- Update aggregate progress ----
        downloaded_size = self._aggregate_downloaded_size()
        progress = 0
        if self.full_size > 0:
            progress = min(downloaded_size / self.full_size, 1)
        self.progressbar.set_fraction(progress)
        self.update_speed_and_time()
        megabytes = 1024 * 1024
        progress_text = _("{downloaded} / {size} ({speed:0.2f}MB/s), {time} remaining").format(
            downloaded=human_size(downloaded_size),
            size=human_size(self.full_size),
            speed=float(self.avg_speed) / megabytes,
            time=self.time_left,
        )
        self._set_text(progress_text)

        # ---- Check if all done ----
        if not self._active_downloads and not self._file_queue:
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.downloader = None
            self.emit("complete", {})
            return False

        return True

    # ------------------------------------------------------------------
    # Speed / ETA (aggregate)
    # ------------------------------------------------------------------

    def update_speed_and_time(self):
        """Update time left and average speed using aggregate throughput."""
        elapsed_time = get_time() - self.time_left_check_time
        if elapsed_time < 1:  # Minimum delay
            return

        downloaded_size = self._aggregate_downloaded_size()
        elapsed_size = downloaded_size - self.last_size
        self.last_size = downloaded_size

        speed = elapsed_size / elapsed_time
        # last 20 speeds
        if len(self.speed_list) >= 20:
            self.speed_list.pop(0)
        self.speed_list.append(speed)

        self.avg_speed = sum(self.speed_list) / len(self.speed_list)
        if self.avg_speed == 0:
            self.time_left = "???"
            return

        average_time_left = (self.full_size - downloaded_size) / self.avg_speed
        minutes, seconds = divmod(average_time_left, 60)
        hours, minutes = divmod(minutes, 60)
        self.time_left_check_time = get_time()
        self.time_left = "%d:%02d:%02d" % (hours, minutes, seconds)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cancel_all(self):
        """Cancel every active download without emitting a signal."""
        for ad in self._active_downloads:
            ad.downloader.cancel()
        self._active_downloads.clear()
        self.downloader = None
        self.cancel_button.set_sensitive(False)

    def _set_text(self, text):
        markup = "<span size='10000'>{}</span>".format(gtk_safe(text))
        self.progress_label.set_markup(markup)
