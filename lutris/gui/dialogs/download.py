from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.dialogs import ModalDialog
from lutris.gui.widgets.download_progress_box import DownloadProgressBox


class DownloadDialog(ModalDialog):
    """Dialog showing a download in progress."""

    def __init__(self, url=None, dest=None, title=None, label=None, downloader=None, parent=None):
        super().__init__(title=title or _("Downloading file"), parent=parent, border_width=10)
        self.set_size_request(485, 104)
        params = {"url": url, "dest": dest, "title": label or _("Downloading %s") % url}
        self.dialog_progress_box = DownloadProgressBox(params, downloader=downloader)

        self.dialog_progress_box.connect("complete", self.download_complete)
        self.dialog_progress_box.connect("cancel", self.download_cancelled)
        self.connect("response", self.on_response)

        self.get_content_area().add(self.dialog_progress_box)
        self.show_all()
        self.dialog_progress_box.start()

    @property
    def downloader(self):
        return self.dialog_progress_box.downloader

    def download_complete(self, _widget, _data):
        self.response(Gtk.ResponseType.OK)
        self.destroy()

    def download_cancelled(self, _widget):
        self.response(Gtk.ResponseType.CANCEL)
        self.destroy()

    def on_response(self, _dialog, response):
        if response == Gtk.ResponseType.DELETE_EVENT:
            self.dialog_progress_box.downloader.cancel()
            self.destroy()
