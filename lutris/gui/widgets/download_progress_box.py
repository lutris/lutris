from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris.gui.dialogs import display_error
from lutris.util.file_downloads import DownloadState, DownloadStatus, FileCollectionDownload, FileDownload
from lutris.util.strings import gtk_safe, human_size


class DownloadProgressBox(Gtk.Box):
    """Shows a download's progress, and lets the user cancel or retry it.

    The download (lutris.util.file_downloads) does the work; this only displays
    it, and re-emits its outcome as the 'complete', 'cancel' and 'error' signals.
    """

    __gsignals__ = {
        "complete": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, download: FileDownload, cancelable: bool = True) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.download = download
        self.cancelable = cancelable
        self.is_complete = False

        self.main_label = self._create_label(download.title)
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_top(5)
        self.progressbar.set_margin_bottom(5)
        self.progressbar.set_margin_right(10)
        self.cancel_button = Gtk.Button.new_with_mnemonic(_("_Cancel"))
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_cancel_clicked)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        self.progress_label = Gtk.Label()
        self.progress_label.set_alignment(0, 0)
        self.file_name_label: Gtk.Label | None = None

        progress_box = Gtk.Box()
        progress_box.pack_start(self.progressbar, True, True, 0)
        if isinstance(download, FileCollectionDownload):
            # Collections name the files being downloaded, under a title with the cancel button
            top_box = Gtk.Box()
            top_box.pack_start(self.main_label, False, False, 0)
            top_box.pack_end(self.cancel_button, False, False, 0)
            self.pack_start(top_box, True, True, 0)
            self.file_name_label = self._create_label("")
            self.pack_start(self.file_name_label, True, True, 0)
        else:
            self.pack_start(self.main_label, True, True, 0)
            progress_box.pack_end(self.cancel_button, False, False, 0)
        self.pack_start(progress_box, False, False, 0)
        self.pack_start(self.progress_label, True, True, 0)

        self.show_all()
        self.cancel_button.hide()

        registration = download.changed.register(self._on_download_changed)
        self.connect("destroy", lambda *_args: registration.unregister())

    @staticmethod
    def _create_label(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_alignment(0, 0)
        label.set_property("wrap", True)
        label.set_margin_bottom(10)
        label.set_selectable(True)
        label.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        return label

    def start(self) -> None:
        """Start the download."""
        self.download.start()

    def cancel_download(self) -> None:
        self.download.cancel()

    def on_cancel_clicked(self, _widget: Gtk.Widget | None = None) -> None:
        """Cancel the download."""
        self.cancel_button.set_sensitive(False)
        self.download.cancel()

    def set_retry_button(self) -> None:
        """Transform the cancel button into a retry button"""
        self.cancel_button.set_label(_("Retry"))
        self.cancel_button.disconnect(self.cancel_cb_id)
        self.cancel_cb_id = self.cancel_button.connect("clicked", self.on_retry_clicked)
        self.cancel_button.set_sensitive(True)

    def on_retry_clicked(self, button: Gtk.Button) -> None:
        button.set_label(_("Cancel"))
        button.disconnect(self.cancel_cb_id)
        self.cancel_cb_id = button.connect("clicked", self.on_cancel_clicked)
        self.download.retry()

    def _on_download_changed(self, state: DownloadState, status: DownloadStatus, error: BaseException | None) -> None:
        if state == DownloadState.DOWNLOADING:
            self.cancel_button.show()
            self.cancel_button.set_sensitive(self.cancelable)
            self._show_status(status)
        elif state == DownloadState.COMPLETED:
            self._show_status(status)
            self.cancel_button.set_sensitive(False)
            self.is_complete = True
            self.emit("complete", {})
        elif state == DownloadState.CANCELLED:
            self.progressbar.set_fraction(0)
            self._set_text(_("Download interrupted"))
            self.cancel_button.set_sensitive(False)
            if error:
                # It couldn't even start
                display_error(error, parent=self.get_toplevel())
            self.emit("cancel")
        elif state == DownloadState.FAILED:
            self.progressbar.set_fraction(0)
            self._set_text(str(error)[:80])
            self.emit("error", error)

    def _show_status(self, status: DownloadStatus) -> None:
        self.progressbar.set_fraction(status.fraction)
        if self.file_name_label:
            self.file_name_label.set_text(", ".join(status.current_files))
        megabytes = 1024 * 1024
        self._set_text(
            _("{downloaded} / {size} ({speed:0.2f}MB/s), {time} remaining").format(
                downloaded=human_size(status.downloaded_size),
                size=human_size(status.full_size),
                speed=status.speed / megabytes,
                time=status.time_left,
            )
        )

    def _set_text(self, text: str) -> None:
        markup = "<span size='10000'>{}</span>".format(gtk_safe(text))
        self.progress_label.set_markup(markup)
