# -*- coding: utf-8 -*-
"""Common message dialogs"""
import os
from gi.repository import Gtk

from lutris.gui.widgets import DownloadProgressBox


from lutris import settings


class AboutDialog(object):
    def __init__(self):
        ui_filename = os.path.join(settings.get_data_path(), 'ui',
                                   'AboutDialog.ui')
        if not os.path.exists(ui_filename):
            ui_filename = None

        builder = Gtk.Builder()
        builder.add_from_file(ui_filename)
        self.dialog = builder.get_object("about_dialog")
        builder.connect_signals(self)

        self.dialog.show_all()

    def on_close(self, *args):
        self.dialog.destroy()


class NoticeDialog(Gtk.MessageDialog):
    """ Displays a message to the user. """
    def __init__(self, message):
        super(NoticeDialog, self).__init__(buttons=Gtk.ButtonsType.OK)
        self.set_markup(message)
        self.run()
        self.destroy()


class ErrorDialog(Gtk.MessageDialog):
    """ Displays an error message. """
    def __init__(self, message):
        super(ErrorDialog, self).__init__(buttons=Gtk.ButtonsType.OK)
        self.set_markup(message)
        self.run()
        self.destroy()


class QuestionDialog(Gtk.MessageDialog):
    """ Asks a question. """
    def __init__(self, settings):
        super(QuestionDialog, self).__init__(
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            message_format=settings['question']
        )
        self.set_title(settings['title'])
        self.result = self.run()
        self.destroy()


class DirectoryDialog(Gtk.FileChooserDialog):
    """Ask the user to select a directory"""
    def __init__(self, message):
        super(DirectoryDialog, self).__init__(
            title=message,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE,
                     Gtk.STOCK_OK, Gtk.ResponseType.OK)
        )
        self.result = self.run()
        self.folder = self.get_current_folder()
        self.destroy()


class FileDialog(Gtk.FileChooserDialog):
    def __init__(self):
        super(FileDialog, self).__init__(
            "Please choose a file", None, Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        response = self.run()
        if response == Gtk.ResponseType.OK:
            self.filename = self.get_filename()
        elif response == Gtk.ResponseType.CANCEL:
            self.filename = False
        self.destroy()


class DownloadDialog(Gtk.Dialog):
    """ Dialog showing a download in progress. """
    def __init__(self, url, dest):
        super(DownloadDialog, self).__init__("Downloading file")
        self.set_size_request(560, 100)
        #self.connect('destroy', self.destroy_cb)
        params = {'url': url, 'dest': dest}
        self.download_progress_box = DownloadProgressBox(params)
        self.download_progress_box.connect('complete', self.download_complete)
        label = Gtk.Label(label='Downloading %s' % url)
        label.set_selectable(True)
        label.set_padding(0, 0)
        label.set_alignment(0.0, 1.0)
        self.vbox.pack_start(label, True, True, 0)
        self.vbox.pack_start(self.download_progress_box, True, False, 0)
        self.show_all()
        self.download_progress_box.start()

    def destroy_cb(self, widget, data=None):
        """Action triggered when window is closed"""
        self.destroy()

    def download_complete(self, _widget, _data):
        self.destroy()

    def download_cancel(self, _widget, _data=None):
        """Action triggered when download is cancelled"""
        #self.download_progress_box.cancel()
        pass
