# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

"""Common message dialogs"""

from gi.repository import Gtk, GObject

from lutris.gui.widgets import DownloadProgressBox


class NoticeDialog(Gtk.MessageDialog):
    """ Displays a message to the user. """
    def __init__(self, message):
        Gtk.MessageDialog.__init__(buttons=Gtk.ButtonsType.OK)
        self.set_markup(message)
        self.run()
        self.destroy()


class ErrorDialog(Gtk.MessageDialog):
    """ Displays an error message. """
    def __init__(self, message):
        Gtk.MessageDialog.__init__(buttons=Gtk.ButtonsType.OK)
        self.set_markup(message)
        self.run()
        self.destroy()


class QuestionDialog(Gtk.MessageDialog):
    """ Asks a question. """
    def __init__(self, settings):
        super(QuestionDialog, self).__init__(
            type=Gtk.MessageType.QUESTION,
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


class DownloadDialog(Gtk.Dialog):
    """ Dialog showing a download in progress. """
    def __init__(self, url, dest):
        GObject.GObject.__init__(self, "Downloading file")
        self.set_size_request(560, 100)
        self.connect('destroy', self.destroy_cb)
        params = {'url': url, 'dest': dest}
        self.download_progress_box = DownloadProgressBox(params)
        label = Gtk.Label(label='Downloading %s' % url)
        label.set_padding(0, 0)
        label.set_alignment(0.0, 1.0)
        self.vbox.pack_start(label, True, True, 0)
        self.vbox.pack_start(self.download_progress_box, True, False, 0)
        self.show_all()
        self.download_progress_box.start()

    def destroy_cb(self, widget, data=None):
        """Action triggered when window is closed"""
        self.download_cancel(None)
        self.destroy()

    def download_cancel(self, _widget, _data=None):
        """Action triggered when download is cancelled"""
        self.download_progress_box.cancel()
