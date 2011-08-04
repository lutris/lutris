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


import sys
import os
import pygtk
import gtk

from lutris.gui.widgets import DownloadProgressBox

class NoticeDialog:
    def __init__(self, message):
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

class ErrorDialog:
    def __init__(self, message):
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
        dialog.set_markup(message)
        dialog.run()
        dialog.destroy()

class QuestionDialog:
    def __init__(self,settings):
        dialog = gtk.MessageDialog(
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_YES_NO,
                message_format=settings['question']
            )
        dialog.set_title(settings['title'])
        self.result = dialog.run()
        dialog.destroy()

class DirectoryDialog:
    """Ask the user to select a directory"""
    def __init__(self, message):
        dialog = gtk.FileChooserDialog(
                title=message,
                action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,
                         gtk.STOCK_OK, gtk.RESPONSE_OK)
            )
        self.result = dialog.run()
        self.folder = dialog.get_current_folder()
        dialog.destroy()

class DownloadDialog(gtk.Dialog):
    def __init__(self, url, dest):
        print "creating download dialog"
        gtk.Dialog.__init__(self, "Downloading file")
        self.quit_gtk = False
        self.set_size_request(560,100)
        self.connect('destroy', self.destroy_cb)
        params = {'url': url, 'dest': dest}
        self.download_progress_box = DownloadProgressBox(params)
        self.download_progress_box.connect('complete', self.download_complete)
        label = gtk.Label('Downloading %s' % url)
        label.set_padding(0,0)
        label.set_alignment(0.0,1.0)
        self.vbox.pack_start(label, True, True, 0)
        self.vbox.pack_start(self.download_progress_box, True,False, 0)
        self.show_all()
        self.download_progress_box.start()

    def destroy_cb(self, widget, data=None):
        self.download_cancel(None)
        self.destroy()
        if self.quit_gtk is True:
            gtk.main_quit()

    def download_cancel(self, widget, data=None):
        self.download_progress_box.cancel()

    def download_complete(self, widget, data=None):
        print "download is complete"
