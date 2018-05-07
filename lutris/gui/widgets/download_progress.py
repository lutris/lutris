from gi.repository import GLib, GObject, Gtk, Pango
from lutris.util.downloader import Downloader


class DownloadProgressBox(Gtk.VBox):
    """Progress bar used to monitor a file download."""
    __gsignals__ = {
        'complete': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_PYOBJECT,)),
        'cancel': (GObject.SignalFlags.RUN_LAST, None,
                   (GObject.TYPE_PYOBJECT,)),
        'error': (GObject.SignalFlags.RUN_LAST, None,
                  (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, params, cancelable=True, downloader=None):
        super(DownloadProgressBox, self).__init__()

        self.downloader = downloader
        self.url = params.get('url')
        self.dest = params.get('dest')
        self.referer = params.get('referer')
        title = params.get('title', "Downloading {}".format(self.url))

        self.main_label = Gtk.Label(title)
        self.main_label.set_alignment(0, 0)
        self.main_label.set_property('wrap', True)
        self.main_label.set_margin_bottom(10)
        self.main_label.set_max_width_chars(70)
        self.main_label.set_selectable(True)
        self.main_label.set_property('ellipsize', Pango.EllipsizeMode.MIDDLE)
        self.pack_start(self.main_label, True, True, 0)

        progress_box = Gtk.Box()

        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(5)
        self.progressbar.set_margin_bottom(5)
        self.progressbar.set_margin_right(10)
        progress_box.pack_start(self.progressbar, True, True, 0)

        self.cancel_button = Gtk.Button.new_with_mnemonic('_Cancel')
        self.cancel_button.connect('clicked', self.cancel)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        progress_box.pack_end(self.cancel_button, False, False, 0)

        self.pack_start(progress_box, False, False, 0)

        self.progress_label = Gtk.Label()
        self.progress_label.set_alignment(0, 0)
        self.pack_start(self.progress_label, True, True, 0)

        self.show_all()

    def start(self):
        """Start downloading a file."""
        if not self.downloader:
            try:
                self.downloader = Downloader(self.url,
                                             self.dest,
                                             referer=self.referer,
                                             overwrite=True)
            except RuntimeError as ex:
                from lutris.gui.dialogs import ErrorDialog
                ErrorDialog(ex.args[0])
                self.emit('cancel', {})
                return

        timer_id = GLib.timeout_add(100, self._progress)
        self.cancel_button.set_sensitive(True)
        if not self.downloader.state == self.downloader.DOWNLOADING:
            self.downloader.start()
        return timer_id

    def cancel(self, _widget=None):
        """Cancel the current download."""
        if self.downloader:
            self.downloader.cancel()
        self.cancel_button.set_sensitive(False)
        self.emit('cancel', {})

    def _progress(self):
        """Show download progress."""
        progress = min(self.downloader.check_progress(), 1)
        if self.downloader.state in [self.downloader.CANCELLED,
                                     self.downloader.ERROR]:
            self.progressbar.set_fraction(0)
            self._set_text("Download interrupted")
            if self.downloader.state == self.downloader.CANCELLED:
                self.emit('cancel', {})
            return False
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = (
            "%0.2f / %0.2fMB (%0.2fMB/s), %s remaining" % (
                float(self.downloader.downloaded_size) / megabytes,
                float(self.downloader.full_size) / megabytes,
                float(self.downloader.average_speed) / megabytes,
                self.downloader.time_left
            )
        )
        self._set_text(progress_text)
        if self.downloader.state == self.downloader.COMPLETED:
            self.cancel_button.set_sensitive(False)
            self.emit('complete', {})
            return False
        return True

    def _set_text(self, text):
        markup = u"<span size='10000'>{}</span>".format(text)
        self.progress_label.set_markup(markup)
