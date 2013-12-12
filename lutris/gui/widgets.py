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
# Ignoring pylint
# E0611 : No name '...' in module '...'
# F0401 : Unable to import '...'
# E1101 : Instance of '...' has no '...' member
# pylint: disable=E0611, F0401, E1101

import os
#import Image

from gi.repository import Gtk, Gdk, GObject, Pango, GdkPixbuf, GLib
from gi.repository.GdkPixbuf import Pixbuf

from lutris.downloader import Downloader
from lutris.constants import COVER_PATH
#from lutris.util.log import logger
from lutris import settings

MISSING_ICON = os.path.join(settings.get_data_path(), 'media/banner.png')
UNAVAILABLE_GAME_OVERLAY = os.path.join(settings.get_data_path(),
                                        'media/unavailable.png')

(COL_ID,
 COL_NAME,
 COL_ICON,
 COL_RUNNER,
 COL_RUNNER_ICON,
 COL_GENRE,
 COL_PLATFORM,
 COL_YEAR) = range(8)


def sort_func(store, a_iter, b_iter, _user_data):
    """Default sort function"""
    a_name = store.get(a_iter, COL_NAME)
    b_name = store.get(b_iter, COL_NAME)

    if a_name > b_name:
        return 1
    elif a_name < b_name:
        return -1
    else:
        return 0


def filter_view(model, _iter, user_data):
    """Filter the game list"""
    filter_text = user_data(None)
    if not filter_text:
        return True
    name = model.get(_iter, COL_NAME)[0]
    if filter_text.lower() in name.lower():
        return True
    else:
        return False


def get_pixbuf_for_game(game_slug, size=(184, 69), is_installed=True):
    width = size[0]
    height = size[1]
    icon_path = os.path.join(settings.DATA_DIR, "banners",
                             "%s.jpg" % game_slug)
    if not os.path.exists(icon_path):
        icon_path = MISSING_ICON
    try:
        pixbuf = Pixbuf.new_from_file_at_size(icon_path, width, height)
    except GLib.GError:
        pixbuf = Pixbuf.new_from_file_at_size(MISSING_ICON, width, height)
    if not is_installed:
        transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            UNAVAILABLE_GAME_OVERLAY, width, height
        )
        transparent_pixbuf = transparent_pixbuf.scale_simple(
            width, height, GdkPixbuf.InterpType.NEAREST
        )
        pixbuf.composite(transparent_pixbuf, 0, 0, width, height,
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf


class IconViewCellRenderer(Gtk.CellRendererText):
    def __init__(self, *args, **kwargs):
        super(IconViewCellRenderer, self).__init__(*args, **kwargs)
        self.props.alignment = Pango.Alignment.CENTER
        self.props.wrap_mode = Pango.WrapMode.WORD
        self.props.xalign = 0.5
        self.props.yalign = 0
        self.props.width = 184
        self.props.wrap_width = 184


class GameStore(object):
    filter_text = ""

    def __init__(self, games, icon_size=(184, 69)):
        self.icon_size = icon_size
        self.store = Gtk.ListStore(str, str, Pixbuf, str,
                                   str, str, str)
        self.store.set_default_sort_func(sort_func)
        self.store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)
        self.fill_store(games)
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(filter_view,
                                          lambda x: self.filter_text)

    def fill_store(self, games):
        self.store.clear()
        for game in games:
            self.add_game(game)

    def add_game(self, game):
        """Adds a game into the view"""
        pixbuf = get_pixbuf_for_game(game.slug, self.icon_size,
                                     is_installed=game.is_installed)
        name = game.name.replace('&', "&amp;")
        self.store.append((game.slug, name, pixbuf, game.runner_name,
                           "Genre", "Platform", "Year"))


class GameView(object):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "filter-updated": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }
    selected_game = None
    current_path = None
    contextual_menu = None
    filter_text = ""
    games = []

    def get_row_by_slug(self, game_slug):
        game_row = None
        for model_row in self.game_store.store:
            if model_row[COL_ID] == game_slug:
                game_row = model_row
        return game_row

    def remove_game(self, removed_id):
        row = self.get_row_by_slug(removed_id)
        if row:
            self.remove_row(row.iter)

    def remove_row(self, model_iter):
        """Remove a game from the treeview."""
        store = self.game_store.store
        store.remove(model_iter)

    def update_filter(self, widget, data=None):
        self.game_store.filter_text = data
        self.get_model().refilter()

    def update_image(self, game_slug, is_installed=False):
        row = self.get_row_by_slug(game_slug)
        if row:
            game_pixpuf = get_pixbuf_for_game(game_slug,
                                              is_installed=is_installed)
            row[2] = game_pixpuf

    def popup_contextual_menu(self, view, event):
        """Contextual menu"""
        if event.button != 3:
            return
        try:
            view.current_path = view.get_path_at_pos(event.x, event.y)
            if type(view) is GameIconView and view.current_path:
                view.select_path(view.current_path)
        except ValueError:
            (_, path) = view.get_selection().get_selected()
            view.current_path = path
        if view.current_path:
            self.contextual_menu.popup(None, None, None, None,
                                       event.button, event.time)


class GameTreeView(Gtk.TreeView, GameView):
    """Show the main list of games"""
    __gsignals__ = GameView.__gsignals__

    def __init__(self, games):
        self.game_store = GameStore(games)
        super(GameTreeView, self).__init__(self.game_store.modelfilter)
        self.set_rules_hint(True)

        # Icon column
        image_cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("", image_cell, pixbuf=COL_ICON)
        column.set_reorderable(True)
        self.append_column(column)

        # Name column
        column = self.setup_text_column("Name", COL_NAME)
        self.append_column(column)
        # Genre column
        #column = self.setup_text_column("Genre", COL_GENRE)
        #self.append_column(column)
        # Platform column
        #column = self.setup_text_column("Platform", COL_PLATFORM)
        #self.append_column(column)
        # Runner column
        column = self.setup_text_column("Runner", COL_RUNNER)
        self.append_column(column)
        # Year column
        #column = self.setup_text_column("Year", COL_YEAR)
        #self.append_column(column)

        self.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        self.connect('row-activated', self.get_selected_game, True)
        self.connect('cursor-changed', self.get_selected_game, False)
        self.connect('filter-updated', self.update_filter)
        self.connect('button-press-event', self.popup_contextual_menu)

    def setup_text_column(self, header, column_id):
        text_cell = Gtk.CellRendererText()
        text_cell.set_padding(4, 10)
        text_cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        text_cell.set_property("width-chars", 40)

        column = Gtk.TreeViewColumn(header, text_cell, markup=column_id)
        column.set_sort_indicator(True)
        column.set_sort_column_id(column_id)
        column.set_resizable(True)
        column.set_reorderable(True)
        return column

    def remove_row(self, model_iter):
        """Remove a game from the treeview."""
        model = self.get_model()
        model.remove(model_iter)

    def sort_rows(self):
        """Sort the game list."""
        model = self.get_model()
        Gtk.TreeModel.sort_new_with_model(model)

    def get_selected_game(self, widget, line=None, column=None, launch=False):
        selection = self.get_selection()
        if not selection:
            return
        model, select_iter = selection.get_selected()
        self.selected_game = model.get_value(select_iter, COL_ID)
        if launch:
            self.emit("game-activated")
        else:
            self.emit("game-selected")


class GameIconView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__
    icon_width = 184
    icon_padding = 1

    def __init__(self, games):
        self.game_store = GameStore(games, icon_size=(184, 69))
        super(GameIconView, self).__init__(self.game_store.modelfilter)
        self.set_columns(1)
        self.set_column_spacing(1)
        self.set_pixbuf_column(COL_ICON)
        iconview_cell_renderer = IconViewCellRenderer()
        self.pack_end(iconview_cell_renderer, False)
        self.add_attribute(iconview_cell_renderer, 'markup', COL_NAME)
        self.set_item_padding(self.icon_padding)

        self.connect('item-activated', self.on_item_activated)
        self.connect('selection-changed', self.on_selection_changed)
        self.connect('filter-updated', self.update_filter)
        self.connect('button-press-event', self.popup_contextual_menu)
        self.connect('size-allocate', self.on_size_allocate)

    def set_fluid_columns(self, width):
        icon_width = self.icon_width + self.icon_padding * 2
        nb_columns = (width / icon_width)
        self.set_columns(nb_columns)

    def on_size_allocate(self, widget, rect):
        """ Recalculate the colum spacing based on total widget width """
        width = self.get_parent().get_allocated_width()
        self.set_fluid_columns(width - 20)
        self.do_size_allocate(widget, rect)

    def on_item_activated(self, view, path):
        self.get_selected_game(True)

    def on_selection_changed(self, view):
        self.get_selected_game(False)

    def get_selected_game(self, launch=False):
        selection = self.get_selected_items()
        if not selection:
            return
        self.current_path = selection[0]
        store = self.get_model()
        self.selected_game = store.get(store.get_iter(self.current_path),
                                       COL_ID)
        if launch:
            self.emit("game-activated")
        else:
            self.emit("game-selected")


class GameCover(Gtk.Image):
    """Widget displaing the selected game's cover"""
    def __init__(self, parent=None):
        super(GameCover, self).__init__()
        self.parent_window = parent
        self.set_from_file(os.path.join(settings.get_data_path(),
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
            self.set_from_file(os.path.join(settings.get_data_path(),
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
                           Gdk.DragAction.COPY | Gdk.DragAction.DEFAULT |
                           Gdk.DragAction.MOVE)

    def on_cover_drop(self, widget, context, x, y, selection, target, ts):
        """Take action based on a drop on the widget."""
        # TODO : Change mouse cursor if no game is selected
        #        of course, it must not be handled here
        file_path = selection.data.strip()
        if not file_path.endswith(('.png', '.jpg', '.gif', '.bmp')):
            return True
        game = self.parent_window.get_selected_game()
        if file_path.startswith('file://'):
            #image_path = file_path[7:]
            #im = Image.open(image_path)
            #im.thumbnail((400, 600), Image.ANTIALIAS)
            #dest_image = os.path.join(COVER_PATH, game + ".jpg")
            #im.save(dest_image, "JPEG")
            pass
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
    __gsignals__ = {
        'complete': (GObject.SignalFlags.RUN_LAST, None,
                     (GObject.TYPE_PYOBJECT,)),
        'cancelrequested': (GObject.SignalFlags.RUN_LAST, None,
                            (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self, params, cancelable=True):
        super(DownloadProgressBox, self).__init__()
        self.downloader = None

        self.progress_box = Gtk.VBox()

        self.progressbar = Gtk.ProgressBar()
        self.progress_box.pack_start(self.progressbar, True, True, 10)
        self.progress_label = Gtk.Label()
        self.progress_box.pack_start(self.progress_label, True, True, 10)
        self.pack_start(self.progress_box, True, True, 10)
        self.progress_box.show_all()

        self.cancel_button = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        if cancelable:
            self.cancel_button.show()
            self.cancel_button.set_sensitive(False)
            self.cancel_button.connect('clicked', self.cancel)
            self.pack_end(self.cancel_button, False, False, 10)

        self.url = params['url']
        self.dest = params['dest']

    def start(self):
        """Start downloading a file."""
        self.downloader = Downloader(self.url, self.dest)
        timer_id = GLib.timeout_add(100, self.progress)
        self.cancel_button.set_sensitive(True)
        self.downloader.start()
        return timer_id

    def progress(self):
        """Show download progress."""
        progress = min(self.downloader.progress, 1)
        if self.downloader.cancelled:
            self.progressbar.set_fraction(0)
            self.progress_label.set_text("Download canceled")
            self.emit('cancelrequested', {})
            return False
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = (
            "%0.2fMb out of %0.2fMb (%0.2fMb/s), %d seconds remaining" % (
                float(self.downloader.downloaded_bytes) / megabytes,
                float(self.downloader.total_bytes) / megabytes,
                float(self.downloader.speed) / megabytes,
                self.downloader.time_remaining
            )
        )
        self.progress_label.set_text(progress_text)
        self.progressbar.set_fraction(progress)
        if progress >= 1.0:
            self.cancel_button.set_sensitive(False)
            self.emit('complete', {})
            return False
        return True

    def cancel(self, _widget):
        """Cancel the current download."""
        if self.downloader:
            self.downloader.cancel()
            self.cancel_button.set_sensitive(False)


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
                if filefilter is not None \
                        and not filename.startswith(filefilter):
                    continue
                self.path_completion.append(
                    [os.path.join(current_path, filename)]
                )
                index += 1
                if index > 15:
                    break

    def select_file(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.entry.set_text(dialog.get_filename())
        dialog.destroy()
