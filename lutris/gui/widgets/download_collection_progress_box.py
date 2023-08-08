from gettext import gettext as _
from urllib.parse import urlparse

from gi.repository import GLib, GObject, Gtk, Pango

from lutris.util.downloader import Downloader
from lutris.util.log import logger
from lutris.util.strings import gtk_safe

class DownloadCollectionProgressBox(Gtk.Box):
    """Progress bar used to monitor a collection of files download."""

    max_retries = 3

    __gsignals__ = {
        "complete": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, )),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, )),
    }

    def __init__(self, mult_files, cancelable=True, downloader=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.downloader = downloader
        self.is_complete = False
        self._file_queue = mult_files.files_list.copy()
        self._file_downlaod = None  # file being downloaded
        self.title = mult_files.human_url
        self.num_files_downloaded = 0
        self.num_files_to_download = mult_files.num_files
        self.num_retries = 0

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

        full_progress_box = Gtk.Box()
        self.full_progressbar = Gtk.ProgressBar(show_text=True)
        self.full_progressbar.set_margin_top(5)
        self.full_progressbar.set_margin_bottom(5)
        self.full_progressbar.set_margin_right(10)
        full_progress_box.pack_start(self.full_progressbar, True, True, 0)

        self.pack_start(full_progress_box, False, False, 0)
        self.update_full_progress()

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

    def update_full_progress(self):
        """Update Full download progress bar"""
        if self.num_files_to_download <= 0:
            self.full_progressbar.pulse()
        else:
            self.full_progressbar.set_fraction(self.num_files_downloaded/self.num_files_to_download)
        self.full_progressbar.set_text(f"{self.num_files_downloaded} / {self.num_files_to_download} {_('Files')}")

    def update_downlaod_file_label(self, file_name):
        """Update file label to file being downloaded"""
        self.file_name_label.set_text(file_name)

    def get_new_file_from_queue(self):
        """Set downloaded file to new file from queue or None if empty"""
        if self._file_queue:
            self._file_downlaod = self._file_queue.pop()
            return
        self._file_downlaod = None

    def start(self):
        """Start downloading a file."""
        if not self._file_queue:
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.emit("complete", {})
            return None
        if not self._file_downlaod:
            self.get_new_file_from_queue()
            self.num_retries = 0
        file = self._file_downlaod
        self.update_downlaod_file_label(file.filename)
        if not self.downloader:
            try:
                self.downloader = Downloader(file.url, file.dest_file, referer=file.referer, overwrite=True)
            except RuntimeError as ex:
                from lutris.gui.dialogs import ErrorDialog

                ErrorDialog(ex.args[0])
                self.emit("cancel")
                return None

        timer_id = GLib.timeout_add(500, self._progress)
        self.cancel_button.show()
        self.cancel_button.set_sensitive(True)
        if not self.downloader.state == self.downloader.DOWNLOADING:
            self.downloader.start()
        return timer_id

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
        progress = min(self.downloader.check_progress(), 1)
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
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = _(
            "{downloaded:0.2f} / {size:0.2f}MB ({speed:0.2f}MB/s), {time} remaining"
        ).format(
            downloaded=float(self.downloader.downloaded_size) / megabytes,
            size=float(self.downloader.full_size) / megabytes,
            speed=float(self.downloader.average_speed) / megabytes,
            time=self.downloader.time_left,
        )
        self._set_text(progress_text)
        if self.downloader.state == self.downloader.COMPLETED:
            self.num_files_downloaded += 1
            self.update_full_progress()
            # set file to None to get next one
            self._file_downlaod = None
            self.downloader = None
            # start the downloader to a new file or finish
            self.start()
            return False
        return True

    def _set_text(self, text):
        markup = "<span size='10000'>{}</span>".format(gtk_safe(text))
        self.progress_label.set_markup(markup)
