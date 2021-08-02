from gettext import gettext as _
from urllib.parse import urlparse

from gi.repository import GLib, GObject, Gtk, Pango

from lutris.util.downloader import Downloader
from lutris.util.log import logger
from lutris.util.strings import gtk_safe


class DownloadProgressBox(Gtk.Box):

    """Progress bar used to monitor a file download."""

    __gsignals__ = {
        "complete": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, )),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT, )),
    }

    def __init__(self, params, cancelable=True, downloader=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.downloader = downloader
        self.is_complete = False
        self.url = params.get("url")
        self.dest = params.get("dest")
        self.referer = params.get("referer")

        self.main_label = Gtk.Label(self.get_title())
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

    def get_title(self):
        """Return the main label text for the widget"""
        parsed = urlparse(self.url)
        return "%s%s" % (parsed.netloc, parsed.path)

    def start(self):
        """Start downloading a file."""
        if not self.downloader:
            try:
                self.downloader = Downloader(self.url, self.dest, referer=self.referer, overwrite=True)
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
        """Show download progress."""
        progress = min(self.downloader.check_progress(), 1)
        if self.downloader.state in [self.downloader.CANCELLED, self.downloader.ERROR]:
            self.progressbar.set_fraction(0)
            if self.downloader.state == self.downloader.CANCELLED:
                self._set_text(_("Download interrupted"))
                self.emit("cancel")
            else:
                self._set_text(str(self.downloader.error)[:80])
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
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.emit("complete", {})
            return False
        return True

    def _set_text(self, text):
        markup = u"<span size='10000'>{}</span>".format(gtk_safe(text))
        self.progress_label.set_markup(markup)
