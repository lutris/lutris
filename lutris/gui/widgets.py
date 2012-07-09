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
"""Misc widgets used in the GUI."""

import os
import Image

from gi.repository import Gtk, Gdk, GObject, Pango, GdkPixbuf, GLib
from gi.repository.GdkPixbuf import Pixbuf

from lutris.downloader import Downloader
from lutris.constants import COVER_PATH
from lutris.util import log
from lutris.settings import get_data_path, DATA_DIR

ICON_SIZE = 24
MISSING_ICON = os.path.join(get_data_path(), 'media/lutris.svg')

(COL_ID,
 COL_NAME,
 COL_ICON,
 COL_RUNNER) = range(4)


def sort_func(store, a_iter, b_iter, user_data):
    (a_name, a_runner) = store.get(a_iter, COL_NAME, COL_RUNNER)
    (b_name, b_runner) = store.get(b_iter, COL_NAME, COL_RUNNER)

    if a_runner > b_runner:
        return 1
    elif a_runner < b_runner:
        return -1
    elif a_name > b_name:
        return 1
    elif a_name < b_name:
        return -1
    else:
        return 0

def create_store():
    store = Gtk.ListStore(str, str, Pixbuf, str)
    store.set_default_sort_func(sort_func)
    store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)
    return store


class GameTreeView(Gtk.TreeView):
    """
    Show the main list of games
    Some code inspired by Ubuntu Software Center
    Many thanks to Michael Vogt

    """
    COL_ICON = 1  # Column number for the icon
    COL_TEXT = 2  # Column number for the description

    def __init__(self, games):
        super(GameTreeView, self).__init__()
        model = Gtk.ListStore(str, Pixbuf, str)
        model.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self.set_model(model)
        image_cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("Runner", image_cell, pixbuf=self.COL_ICON)
        self.append_column(column)
        text_cell = Gtk.CellRendererText()
        text_cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        column = Gtk.TreeViewColumn("Game", text_cell, markup=self.COL_TEXT)
        self.append_column(column)
        if games:
            for game in sorted(games):
                self.add_row(game)

    def add_row(self, game):
        """Add a game in the treeview."""

        model = self.get_model()
        label = "%s \n<small>%s</small>" % \
                (game['name'], game['runner'])
        icon_path = os.path.join(get_data_path(),
                                 'media/runner_icons',
                                 game['runner'] + '.png')
        pix = Pixbuf.new_from_file_at_size(icon_path, ICON_SIZE, ICON_SIZE)
        row = model.append([game['id'], pix, label])
        return row

    def remove_row(self, model_iter):
        """Remove a game from the treeview."""
        model = self.get_model()
        model.remove(model_iter)

    def sort_rows(self):
        """Sort the game list."""
        model = self.get_model()
        Gtk.TreeModel.sort_new_with_model(model)


class GameIconView(Gtk.IconView):
    def __init__(self, games):
        super(GameIconView, self).__init__()
        self.games = games if games else []
        store = create_store()
        self.fill_store(store)
        self.set_model(store)
        self.set_text_column(COL_NAME)
        self.set_pixbuf_column(COL_ICON)

    def fill_store(self, store):
        store.clear()
        for game in self.games:
            pixbuf = self.icon_to_pixbuf(game["id"])
            store.append((game["id"], game["name"], pixbuf, game["runner"]))

    def icon_to_pixbuf(self, game_id):
        icon_path = os.path.join(DATA_DIR, "icons", "%s.png" % game_id)
        if not os.path.exists(icon_path):
            icon_path = MISSING_ICON
        try:
            pixbuf = Pixbuf.new_from_file_at_size(icon_path, 128, 128)
        except GLib.GError:
            pixbuf = Pixbuf.new_from_file_at_size(MISSING_ICON, 128, 128)
        return pixbuf


class GameCover(Gtk.Image):
    """Widget displaing the selected game's cover"""
    def __init__(self, parent=None):
        super(GameCover, self).__init__()
        self.parent_window = parent
        self.set_from_file(os.path.join(get_data_path(),
                                        "media/background.png"))
        self.connect('drag_data_received', self.on_cover_drop)

    def set_game_cover(self, name):
        """Change the cover currently displayed."""
        cover_file = os.path.join(COVER_PATH, name + ".jpg")
        if os.path.exists(cover_file):
            #Resize the image
            cover_pixbuf = Pixbuf.new_from_file(cover_file)
            dest_w = 250.0
            height = cover_pixbuf.get_height()
            width = cover_pixbuf.get_width()
            dest_h = height * (dest_w / width)
            self.set_from_pixbuf(cover_pixbuf.scale_simple(
                int(dest_w),
                int(dest_h),
                GdkPixbuf.InterpType.BILINEAR
            ))
            return
        else:
            self.set_from_file(os.path.join(get_data_path(),
                                            "media/background.png"))

    def desactivate_drop(self):
        """Deactivate DnD for the widget."""
        self.drag_dest_unset()

    def activate_drop(self):
        """Activate DnD for the widget."""
        targets = [('text/plain', 0, 0),
                   ('text/uri-list', 0, 0),
                   ('text/html', 0, 0),
                   ('text/unicode', 0, 0),
                   ('text/x-moz-url', 0, 0)]
        self.drag_dest_set(Gtk.DestDefaults.ALL, targets,
            Gdk.DragAction.COPY | Gdk.DragAction.DEFAULT | Gdk.DragAction.MOVE)

    def on_cover_drop(self, widget, context, x, y, selection, target, ts):
        """Take action based on a drop on the widget."""
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


class DownloadProgressBox(Gtk.HBox):
    """Progress bar used to monitor a file download."""
    __gsignals__ = {'complete': (GObject.SignalFlags.RUN_LAST,
                                 None,
                                 (GObject.TYPE_PYOBJECT,)),
                    'cancelrequested': (GObject.SignalFlags.RUN_LAST,
                                         None,
                                         (GObject.TYPE_PYOBJECT,))}

    def __init__(self, params, cancelable=True):
        GObject.GObject.__init__(self, False, 2)
        self.downloader = None
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.show()
        self.pack_start(self.progressbar, True)
        self.cancel_button = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        if cancelable:
            self.cancel_button.show()
        self.cancel_button.set_sensitive(False)
        self.cancel_button.connect('clicked', self.__stop_download)
        self.pack_end(self.cancel_button, False)

        self.url = params['url']
        self.dest = params['dest']

    def start(self):
        """Start downloading a file."""
        log.logger.debug("starting to download %s" % self.url)
        self.downloader = Downloader(self.url, self.dest)
        timer_id = GObject.timeout_add(100, self.progress)
        self.cancel_button.set_sensitive(True)
        self.downloader.start()
        return timer_id

    def progress(self):
        """Show download progress."""
        progress = min(self.downloader.progress, 1)
        self.progressbar.set_fraction(progress)
        percent = progress * 100
        self.progressbar.set_text("%d %%" % percent)
        if progress >= 1.0:
            log.logger.debug("download of %s has completed" % self.url)
            self.cancel_button.set_sensitive(False)
            self.emit('complete', {})
            return False
        return True

    def __stop_download(self):
        """Stop the current download."""
        self.downloader.kill = True
        self.cancel_button.set_sensitive(False)

    def cancel(self):
        """Cancel the current download."""
        print "cancelling download"
        self.downloader.kill()


class FileChooserEntry(Gtk.Box):
    def __init__(self, action=Gtk.FileChooserAction.SELECT_FOLDER,
                 default=None):
        super(FileChooserEntry, self).__init__()

        self.entry = Gtk.Entry()
        if default:
            self.entry.set_text(default)
        self.pack_start(self.entry, True, True, 0)

        self.path_completion = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion()
        completion.set_model(self.path_completion)
        completion.set_text_column(0)
        self.entry.set_completion(completion)
        self.entry.connect("changed", self.entry_changed)

        button = Gtk.Button()
        button.set_label("Browse...")
        button.connect('clicked', self.open_filechooser, action, default)
        self.add(button)

    def open_filechooser(self, widget, action, default):
        dlg = Gtk.FileChooserDialog(
            "Select folder", None, action,
            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        if default and os.path.exists(default):
            dlg.set_current_folder(default)
        dlg.connect('response', self.select_file)
        dlg.run()

    def entry_changed(self, widget):
        self.path_completion.clear()
        current_path = widget.get_text()
        if not current_path:
            current_path = "/"
        if not os.path.exists(current_path):
            current_path, filefilter = os.path.split(current_path)
        else:
            filefilter = None
        if os.path.isdir(current_path):
            index = 0
            for filename in sorted(os.listdir(current_path)):
                if filename.startswith("."):
                    continue
                if filefilter is not None and \
                   not filename.startswith(filefilter):
                    continue
                self.path_completion.append(
                    [os.path.join(current_path, filename)]
                )
                index = index + 1
                if index > 15:
                    break

    def select_file(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.entry.set_text(dialog.get_filename())
        dialog.destroy()
