import time
from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk, Pango

from lutris.util.downloader import Downloader
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size

# Same reason as Downloader
get_time = time.monotonic


class DownloadCollectionProgressBox(Gtk.Box):
    """Progress bar used to monitor a collection of files download."""

    max_retries = 3

    __gsignals__ = {
        "complete": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, file_collection, cancelable=True, downloader=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.downloader = downloader
        self.is_complete = False
        self._file_queue = file_collection.files_list.copy()
        self._file_download = None  # file being downloaded
        self.title = file_collection.human_url
        self.num_files_downloaded = 0
        self.num_files_to_download = file_collection.num_files
        self.num_retries = 0
        self.full_size = file_collection.full_size
        self.current_size = 0
        self.time_left = "00:00:00"
        self.time_left_check_time = 0
        self.last_size = 0
        self.avg_speed = 0
        self.speed_list = []

        top_box = Gtk.Box()
        self.main_label = Gtk.Label(self.title)
        self.main_label.set_alignment(0, 0)
        self.main_label.set_property("wrap", True)
        self.main_label.set_margin_bottom(10)
        self.main_label.set_selectable(True)
        self.main_label.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        top_box.pack_start(self.main_label, False, False, 0)

        self.cancel_button = Gtk.Button.new_with_mnemonic(_("_Cancel"))
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_cancel_clicked)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        top_box.pack_end(self.cancel_button, False, False, 0)

        self.pack_start(top_box, True, True, 0)

        self.file_name_label = Gtk.Label()
        self.file_name_label.set_alignment(0, 0)
        self.file_name_label.set_property("wrap", True)
        self.file_name_label.set_margin_bottom(10)
        self.file_name_label.set_selectable(True)
        self.file_name_label.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        self.pack_start(self.file_name_label, True, True, 0)

        progress_box = Gtk.Box()
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(5)
        self.progressbar.set_margin_bottom(5)
        self.progressbar.set_margin_right(10)
        progress_box.pack_start(self.progressbar, True, True, 0)

        self.pack_start(progress_box, False, False, 0)

        self.progress_label = Gtk.Label()
        self.progress_label.set_alignment(0, 0)
        self.pack_start(self.progress_label, True, True, 0)

        self.show_all()
        self.cancel_button.hide()

    def update_download_file_label(self, file_name):
        """Update file label to file being downloaded"""
        self.file_name_label.set_text(file_name)

    def get_next_file_from_queue(self):
        """Returns the file to download; if there isn't one this will pull the next one
        from the queue and return that. If there are none there, this returns None."""
        if not self._file_download:
            if not self._file_queue:
                return None

            self._file_download = self._file_queue.pop()
            self.num_retries = 0

        return self._file_download

    def start(self):
        """Start downloading a file."""
        file = self.get_next_file_from_queue()
        if not file:
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.emit("complete", {})
            return

        self.update_download_file_label(file.filename)
        if not self.downloader:
            try:
                self.downloader = Downloader(file.url, file.dest_file, referer=file.referer, overwrite=True)
            except RuntimeError as ex:
                from lutris.gui.dialogs import ErrorDialog

                ErrorDialog(ex, parent=self.get_toplevel())
                self.emit("cancel")
                return

        GLib.timeout_add(500, self._progress)
        self.cancel_button.show()
        self.cancel_button.set_sensitive(True)
        if not self.downloader.state == self.downloader.DOWNLOADING:
            self.downloader.start()

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
        self.downloader.reset()
        self.start()

    def on_cancel_clicked(self, _widget=None):
        """Cancel the current download."""
        logger.debug("Download cancel requested")
        if self.downloader:
            self.downloader.cancel()
        self.cancel_button.set_sensitive(False)
        self.emit("cancel")

    def _progress(self):
        """Show download progress of current file."""
        if self.downloader.state in [self.downloader.CANCELLED, self.downloader.ERROR]:
            self.progressbar.set_fraction(0)
            if self.downloader.state == self.downloader.CANCELLED:
                self._set_text(_("Download interrupted"))
                self.emit("cancel")
            else:
                if self.num_retries > self.max_retries:
                    self._set_text(str(self.downloader.error)[:80])
                    self.emit("error")
                    return False
                self.num_retries += 1
                if self.downloader:
                    self.downloader.reset()
                    self.start()
            return False
        downloaded_size = self.current_size + self.downloader.downloaded_size
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
        if self.downloader.state == self.downloader.COMPLETED:
            self.num_files_downloaded += 1
            self.current_size += self.downloader.downloaded_size
            # set file to None to get next one
            self._file_download = None
            self.downloader = None
            # start the downloader to a new file or finish
            self.start()
            return False
        return True

    def update_speed_and_time(self):
        """Update time left and average speed."""
        elapsed_time = get_time() - self.time_left_check_time
        if elapsed_time < 1:  # Minimum delay
            return

        if not self.downloader:
            self.time_left = "???"
            return

        downloaded_size = self.current_size + self.downloader.downloaded_size
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

    def _set_text(self, text):
        markup = "<span size='10000'>{}</span>".format(gtk_safe(text))
        self.progress_label.set_markup(markup)
