# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2010 Mathieu Comandon <strycore@gmail.com>
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

import os
import gtk
import gobject
import pango
import Image
from lutris.downloader import Downloader
from lutris.constants import COVER_PATH, DATA_PATH
import lutris.constants

ICON_SIZE = 24
MISSING_APP_ICON = "/usr/share/icons/gnome/24x24/categories/applications-other.png"

class GameTreeView(gtk.TreeView):
    """
    Show the main list of games
    Some code inspired by Ubuntu Software Center
    Many thanks to Michael Vogt

    """
    COL_ICON = 1 # Column number for the icon
    COL_TEXT = 2 # Column number for the description

    def __init__(self, games):
        super(GameTreeView, self).__init__()
        model = gtk.ListStore(str,gtk.gdk.Pixbuf, str)
        model.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.set_model(model)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Runner", tp, pixbuf=self.COL_ICON)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn("Game", tr, markup=self.COL_TEXT)
        self.append_column(column)
        for game in sorted(games):
            self.add_row(game)

    def add_row(self, game):
        model = self.get_model()
        s = "%s \n<small>%s</small>" % (game['name'], game['runner'])
        icon_path = os.path.join(lutris.constants.DATA_PATH,
                                 'media/runner_icons',
                                 game['runner'] + '.png')
        pix = gtk.gdk.pixbuf_new_from_file_at_size(icon_path,
                                                   ICON_SIZE, ICON_SIZE)
        row = model.append([game['id'], pix, s,])
        return row

    def remove_row(self, model_iter):
        model = self.get_model()
        model.remove(model_iter)

    def sort_rows(self):
        model = self.get_model()
        gtk.TreeModelSort(model)

class GameCover(gtk.Image):
    def __init__(self, parent=None):
        super(GameCover, self).__init__()
        self.parent_window = parent
        self.set_from_file(os.path.join(DATA_PATH, "media/background.png"))
        self.connect('drag_data_received', self.on_cover_drop)

    def set_game_cover(self, name):
        coverFile = os.path.join(COVER_PATH, name + ".jpg")
        if os.path.exists(coverFile):
            #Resize the image
            cover_pixbuf = gtk.gdk.pixbuf_new_from_file(coverFile)
            dest_w = 250.0
            h = cover_pixbuf.get_height()
            w = cover_pixbuf.get_width()
            dest_h = h * (dest_w / w)
            self.set_from_pixbuf(cover_pixbuf.scale_simple(
                int(dest_w),
                int(dest_h),
                gtk.gdk.INTERP_BILINEAR
            ))
            return
        else:
            self.set_from_file(os.path.join(DATA_PATH, "media/background.png"))

    def desactivate_drop(self):
        self.drag_dest_unset()

    def activate_drop(self):
        targets = [('text/plain',0, 0),
                   ('text/uri-list',0, 0),
                   ('text/html',0, 0),
                   ('text/unicode',0, 0),
                   ('text/x-moz-url',0, 0)
                   ]
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, targets,
            gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)

    def on_cover_drop(self, widget, context, x, y, selection, target, ts):
        # TODO : Change mouse cursor if no game is selected
        #        of course, it must not be handled here
        file_path = selection.data.strip()
        if not file_path.endswith(('.png', '.jpg', '.gif', '.bmp')):
            return True
        game = self.parent_window.get_selected_game()
        if file_path.startswith('file://'):
            image_path = file_path[7:]
            im = Image.open(image_path)
            im.thumbnail((400, 600), Image.ANTIALIAS)
            dest_image = os.path.join(COVER_PATH, game + ".jpg")
            im.save(dest_image, "JPEG")
        elif file_path.startswith('http://'):
            # TODO : Download file to cache directory
            pass
        else:
            # TODO : Handle smb:, stuff like that
            return True
        self.set_game_cover(game)
        return True

class DownloadProgressBox(gtk.HBox):
    __gsignals__ = {'complete' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
        (gobject.TYPE_PYOBJECT,)),
        'cancelrequested' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
        (gobject.TYPE_PYOBJECT,))
        }

    def __init__(self, params, cancelable=True):

        gtk.HBox.__init__(self, False, 2)

        self.progressbar = gtk.ProgressBar()
        self.progressbar.show()
        self.pack_start(self.progressbar, True)

        self.cancel_button = gtk.Button(stock=gtk.STOCK_CANCEL)
        if cancelable:
            self.cancel_button.show()
        self.cancel_button.set_sensitive(False)
        self.cancel_button.connect('clicked', self.__stop_download)
        self.pack_end(self.cancel_button, False)

        self.url = params['url']
        self.dest = params['dest']

    def start(self):
        print "starting to download %s" % self.url
        self.downloader = Downloader(self.url, self.dest)
        self.timer_id = gobject.timeout_add(100, self.progress)
        self.cancel_button.set_sensitive(True)
        self.downloader.start()

    def progress(self):
        progress = min(self.downloader.progress, 1)
        self.progressbar.set_fraction(progress)
        percent = progress * 100
        self.progressbar.set_text("%d %%" % percent)
        if progress >= 1.0:
            print "download has completed"
            self.cancel_button.set_sensitive(False)
            self.emit('complete', {})
            return False
        return True

    def __stop_download(self, widget):
        self.downloader.kill = True
        self.cancel_button.set_sensitive(False)
        #self.downloader = None

    def cancel(self):
        print "cancelling download"
        self.downloader.kill()
