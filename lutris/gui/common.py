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

import pygtk
import gtk
from lutris.gui.widgets import DownloadProgressBar

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
    def __init__(self, message):
        dialog = gtk.FileChooserDialog(
                title=message,
                action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,
                         gtk.STOCK_OK, gtk.RESPONSE_OK)
            )
        self.result = dialog.run()
        self.folder =  dialog.get_current_folder()
        dialog.destroy()

class DownloadDialog(gtk.Dialog):
    def __init__(self, url, dest):
        gtk.Dialog.__init__(self)
        self.connect('destroy', self.destroy_cb)
        self.download_progress_bar = DownloadProgressBar(url, dest)
        label = gtk.Label('Downloading %s' % url)
        button = gtk.Button("start")
        button.connect('clicked', self.start)
        self.vbox.pack_start(label)
        self.vbox.pack_start(button)
        self.vbox.pack_start(self.download_progress_bar)
        self.show_all()

    def destroy_cb(self, widget):
        self.destroy()

    def start(self, widget):
        self.download_progress_bar.start()

if __name__ == "__main__":
    dd = DownloadDialog("http://strycore.com/games/quake/quake.zip", "/home/strider/quake.zip")
    gtk.gdk.threads_init()
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()
