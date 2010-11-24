# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2010 Mathieu Comandon strycore@gmail.com
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
import gio
import pango
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
        icon_path = os.path.join(lutris.constants.DATA_PATH, 'media/runner_icons', game['runner'] + '.png')
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


class DownloadProgressBar(gtk.ProgressBar):
    def __init__(self, url, dest):
        super(DownloadProgressBar, self).__init__()
        # TODO Get some code from Quickly widgets
