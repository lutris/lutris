import os
from gettext import gettext as _
from typing import Optional
from urllib.parse import urlparse

from gi.repository import GObject, Gtk, Pango

from lutris.gui.dialogs import display_error
from lutris.util.downloader import Downloader
from lutris.util.jobs import schedule_repeating_at_idle
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size


class DownloadProgressBox(Gtk.Box):
    """Progress bar used to monitor a file download."""

    __gsignals__ = {
        "complete": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(
        self,
        url: str,
        dest: str,
        temp: str = None,
        referer: Optional[str] = None,
        title: Optional[str] = None,
        cancelable: bool = True,
        downloader: Optional[Downloader] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self._downloader = downloader
        self.is_complete = False
        self.url = url
        self.dest = dest
        self.temp = temp or (dest + ".tmp")
        self.referer = referer

        if not title:
            parsed_url = urlparse(url)
            title = "%s%s" % (parsed_url.netloc, parsed_url.path)

        self.main_label = Gtk.Label(label=title)
        self.main_label.set_alignment(0, 0)
        self.main_label.set_property("wrap", True)
        self.main_label.set_margin_bottom(10)
        # self.main_label.set_max_width_chars(70)
        self.main_label.set_selectable(True)
        self.main_label.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        self.pack_start(self.main_label, True, True, 0)

        progress_box = Gtk.Box()

        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(5)
        self.progressbar.set_margin_bottom(5)
        self.progressbar.set_margin_right(10)
        progress_box.pack_start(self.progressbar, True, True, 0)

        self.cancel_button = Gtk.Button.new_with_mnemonic(_("_Cancel"))
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_cancel_clicked)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        progress_box.pack_end(self.cancel_button, False, False, 0)

        self.pack_start(progress_box, False, False, 0)

        self.progress_label = Gtk.Label()
        self.progress_label.set_alignment(0, 0)
        self.pack_start(self.progress_label, True, True, 0)

        self.show_all()
        self.cancel_button.hide()

        if os.path.exists(self.temp):
            os.remove(self.temp)

    @property
    def downloader(self) -> Downloader:
        if not self._downloader:
            self._downloader = Downloader(self.url, self.temp, referer=self.referer, overwrite=True)
        return self._downloader

    def cancel_download(self):
        if self._downloader:
            self._downloader.cancel()

    def start(self) -> None:
        """Start downloading a file."""
        try:
            downloader = self.downloader
        except RuntimeError as ex:
            display_error(ex, parent=self.get_toplevel())
            self.emit("cancel")
            return None

        schedule_repeating_at_idle(self._progress, interval_seconds=0.5)
        self.cancel_button.show()
        self.cancel_button.set_sensitive(True)
        if not downloader.state == downloader.DOWNLOADING:
            downloader.start()

    def set_retry_button(self):
        """Transform the cancel button into a retry button"""
        self.cancel_button.set_label(_("Retry"))
        self.cancel_button.disconnect(self.cancel_cb_id)
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_retry_clicked)
        self.cancel_button.set_sensitive(True)

    def on_retry_clicked(self, button):
        logger.debug("Retrying download")
        button.set_label(_("Cancel"))
        button.disconnect(self.cancel_cb_id)
        self.cancel_cb_id = button.connect("clicked", self.on_cancel_clicked)
        self.downloader.reset()
        self.start()

    def on_cancel_clicked(self, _widget=None):
        """Cancel the current download."""
        logger.debug("Download cancel requested")
        self.cancel_download()
        self.cancel_button.set_sensitive(False)
        self.emit("cancel")

    def _progress(self) -> bool:
        """Show download progress."""
        downloader = self.downloader
        progress = min(downloader.check_progress(), 1)
        if downloader.state in [downloader.CANCELLED, downloader.ERROR]:
            self.progressbar.set_fraction(0)
            if downloader.state == downloader.CANCELLED:
                self._set_text(_("Download interrupted"))
                self.emit("cancel")
            else:
                self._set_text(str(downloader.error)[:80])
                self.emit("error", downloader.error)
            return False
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = _("{downloaded} / {size} ({speed:0.2f}MB/s), {time} remaining").format(
            downloaded=human_size(downloader.downloaded_size),
            size=human_size(downloader.full_size),
            speed=float(downloader.average_speed) / megabytes,
            time=downloader.time_left,
        )
        self._set_text(progress_text)
        if downloader.state == downloader.COMPLETED:
            os.rename(self.temp, self.dest)
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.emit("complete", {})
            return False
        return True

    def _set_text(self, text):
        markup = "<span size='10000'>{}</span>".format(gtk_safe(text))
        self.progress_label.set_markup(markup)
