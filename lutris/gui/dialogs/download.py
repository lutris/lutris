# Standard Library
from gettext import gettext as _

# Third Party Libraries
from gi.repository import Gtk

# Lutris Modules
from lutris.gui.widgets.download_progress import DownloadProgressBox


class DownloadDialog(Gtk.Dialog):

    """Dialog showing a download in progress."""

    def __init__(self, url=None, dest=None, title=None, label=None, downloader=None):
        Gtk.Dialog.__init__(self, title or _("Downloading file"))
        self.set_size_request(485, 104)
        self.set_border_width(12)
        params = {"url": url, "dest": dest, "title": label or _("Downloading %s") % url}
        self.download_box = DownloadProgressBox(params, downloader=downloader)

        self.download_box.connect("complete", self.download_complete)
        self.download_box.connect("cancel", self.download_cancelled)
        self.connect("response", self.on_response)

        self.get_content_area().add(self.download_box)
        self.show_all()
        self.download_box.start()

    def download_complete(self, _widget, _data):
        self.response(Gtk.ResponseType.OK)
        self.destroy()

    def download_cancelled(self, _widget, data):
        self.response(Gtk.ResponseType.CANCEL)
        self.destroy()

    def on_response(self, _dialog, response):
        if response == Gtk.ResponseType.DELETE_EVENT:
            self.download_box.downloader.cancel()
            self.destroy()
