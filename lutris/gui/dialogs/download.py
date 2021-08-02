from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.widgets.download_progress_box import DownloadProgressBox


class DownloadDialog(Gtk.Dialog):
    """Dialog showing a download in progress."""

    def __init__(self, url=None, dest=None, title=None, label=None, downloader=None):
        Gtk.Dialog.__init__(self, title or _("Downloading file"))
        self.set_size_request(485, 104)
        self.set_border_width(12)
        params = {"url": url, "dest": dest, "title": label or _("Downloading %s") % url}
        self.dialog_progress_box = DownloadProgressBox(params, downloader=downloader)

        self.dialog_progress_box.connect("complete", self.download_complete)
        self.dialog_progress_box.connect("cancel", self.download_cancelled)
        self.connect("response", self.on_response)

        self.get_content_area().add(self.dialog_progress_box)
        self.show_all()
        self.dialog_progress_box.start()

    def download_complete(self, _widget, _data):
        self.response(Gtk.ResponseType.OK)
        self.destroy()

    def download_cancelled(self, _widget, data):
        self.response(Gtk.ResponseType.CANCEL)
        self.destroy()

    def on_response(self, _dialog, response):
        if response == Gtk.ResponseType.DELETE_EVENT:
            self.dialog_progress_box.downloader.cancel()
            self.destroy()


def simple_downloader(url, destination, callback, callback_args=None):
    """Basic downloader with a DownloadDialog"""
    if not callback_args:
        callback_args = {}
    dialog = DownloadDialog(url, destination)
    dialog.run()
    return callback(**callback_args)
