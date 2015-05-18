# -*- coding:Utf-8 -*-
"""Misc widgets used in the GUI."""
import os
from backports.functools_lru_cache import lru_cache # TODO: Bundle

from gi.repository import Gtk, GObject, Pango, GdkPixbuf, GLib
from gi.repository.GdkPixbuf import Pixbuf

from lutris import settings
from lutris.gui.cellrenderers import GridViewCellRendererText
from lutris.downloader import Downloader
from lutris.util import datapath
# from lutris.util.log import logger
from lutris.util.system import reverse_expanduser

PADDING = 5
DEFAULT_BANNER = os.path.join(datapath.get(), 'media/default_banner.png')
DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')
UNAVAILABLE_GAME_OVERLAY = os.path.join(datapath.get(),
                                        'media/unavailable.png')
BANNER_SIZE = (184, 69)
BANNER_SMALL_SIZE = (120, 45)
ICON_SIZE = (32, 32)
(
    COL_ID,
    COL_NAME,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER,
    COL_INSTALLED,
) = range(6)


def get_runner_icon(runner_name, format='image', size=None):
    icon_path = os.path.join(datapath.get(), 'media/runner_icons',
                             runner_name + '.png')
    if format == 'image':
        icon = Gtk.Image()
        icon.set_from_file(icon_path)
    elif format == 'pixbuf' and size:
        icon = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path,
                                                      size[0], size[1])
    else:
        raise ValueError("Invalid arguments")
    return icon


@lru_cache(maxsize=3)
def get_overlay(size):
    x, y = size
    transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
        UNAVAILABLE_GAME_OVERLAY, x, y
    )
    transparent_pixbuf = transparent_pixbuf.scale_simple(
        x, y, GdkPixbuf.InterpType.NEAREST
    )
    return transparent_pixbuf


@lru_cache(maxsize=6)
def get_default(icon, size):
    x, y = size
    return Pixbuf.new_from_file_at_size(icon, x, y)

# Caching here really gets us far, the memory usage should be acceptable
@lru_cache(maxsize=1500)
def get_pixbuf_for_game(game_slug, icon_type="banner", is_installed=True):
    if icon_type in ("banner", "banner_small"):
        size = BANNER_SIZE if icon_type == "banner" else BANNER_SMALL_SIZE
        default_icon = DEFAULT_BANNER
        icon_path = os.path.join(settings.BANNER_PATH,
                                 "%s.jpg" % game_slug)
    elif icon_type == "icon":
        size = ICON_SIZE
        default_icon = DEFAULT_ICON
        icon_path = os.path.join(settings.ICON_PATH,
                                 "lutris_%s.png" % game_slug)

    if not os.path.exists(icon_path):
        pixbuf = get_default(default_icon, size)
    else:
        try:
            pixbuf = Pixbuf.new_from_file_at_size(icon_path, size[0], size[1])
        except GLib.GError:
            pixbuf = get_default(default_icon, size)
    if not is_installed:
        transparent_pixbuf = get_overlay(size).copy()
        pixbuf.composite(transparent_pixbuf, 0, 0, size[0], size[1],
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf


class ContextualMenu(Gtk.Menu):
    menu_labels = {
        'play': "Play",
        'install': "Install",
        'add': "Add manually",
        'configure': "Configure",
        'browse': "Browse files",
        'desktop-shortcut': "Create desktop shortcut",
        'menu-shortcut': "Create application menu shortcut",
        'remove': "Remove",
    }

    def __init__(self, callbacks):
        super(ContextualMenu, self).__init__()
        for callback in callbacks:
            name = callback[0]
            label = self.menu_labels[name]
            action = Gtk.Action(name=name, label=label,
                                tooltip=None, stock_id=None)
            action.connect('activate', callback[1])
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)
        self.show_all()

    def popup(self, event, game_row):
        is_installed = game_row[COL_INSTALLED]
        hide_when_installed = ('add', )
        hide_when_not_installed = ('play', 'configure', 'desktop-shortcut',
                                   'menu-shortcut', 'browse')

        for menuitem in self.get_children():
            action = menuitem.action_id
            if is_installed:
                menuitem.set_visible(action not in hide_when_installed)
            else:
                menuitem.set_visible(action not in hide_when_not_installed)

        super(ContextualMenu, self).popup(None, None, None, None,
                                          event.button, event.time)


class GameStore(GObject.Object):
    __gsignals__ = {
        "games-loaded": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "icons-changed": (GObject.SIGNAL_RUN_FIRST, None, (str,))
    }
    def __init__(self, games, filter_text='', filter_runner='', icon_type=None,
                 filter_installed=False):
        GObject.Object.__init__(self)
        self.filter_text = filter_text
        self.filter_runner = filter_runner
        self.filter_installed = filter_installed
        self.icon_type = icon_type
        self.store = Gtk.ListStore(str, str, Pixbuf, str, str, bool)
        self.store.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)
        self.games = games
        if games:
            self.fill_store(games)
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(self.filter_view)
        self.is_loading = False

    @property
    def n_games(self):
        return len(self.store)

    def filter_view(self, model, _iter, filter_data=None):
        """Filter the game list."""
        if self.filter_installed:
            installed = model.get_value(_iter, COL_INSTALLED)
            if not installed:
                return False
        if self.filter_text:
            name = model.get_value(_iter, COL_NAME)
            if not self.filter_text.lower() in name.lower():
                return False
        if self.filter_runner:
            runner = model.get_value(_iter, COL_RUNNER)
            if not self.filter_runner == runner:
                return False
        return True

    def fill_store(self, games):
        assert(not self.is_loading) # Should only happen once
        assert(not self.games)
        self.games = games
        self.is_loading = True
        adder = self._add_games_idle(games)
        # Avoiding blocking the UI for multiple iterations
        GLib.idle_add(adder.next)

    def _add_games_idle(self, games):
        for game in games:
            self.add_game(game)
            yield True
        self.is_loading = False
        self.emit('games-loaded')
        yield False

    def add_game(self, game):
        """Add a game into the store."""
        if not game.name:
            return
        pixbuf = get_pixbuf_for_game(game.slug, self.icon_type,
                                     is_installed=game.is_installed)
        self.store.append(
            (game.slug, game.name, pixbuf, str(game.year), game.runner_name,
             game.is_installed)
        )

    def get_row_by_slug(self, game_slug):
        game_row = None
        for model_row in self.store:
            if model_row[COL_ID] == game_slug:
                game_row = model_row
        return game_row

    def remove_game(self, removed_id):
        row = self.get_row_by_slug(removed_id)
        if row:
            self.store.remove(row.iter)

    def set_installed(self, game):
        """Update a game row to show as installed"""
        row = self.get_row_by_slug(game.slug)
        if not row:
            self.add_game(game)
        else:
            row[COL_RUNNER] = game.runner_name
            self.update_image(game.slug, is_installed=True)

    def set_uninstalled(self, game_slug):
        """Update a game row to show as uninstalled"""
        row = self.get_row_by_slug(game_slug)
        row[COL_RUNNER] = ''
        self.update_image(game_slug, is_installed=False)

    def update_row(self, game):
        """Update game informations.

        :param dict game: Dict holding game details
        """
        row = self.get_row_by_slug(game['slug'])
        if row:
            row[COL_YEAR] = str(game['year'])
            self.update_image(game['slug'], row[COL_INSTALLED])

    def update_image(self, game_slug, is_installed=False):
        """Update game icon."""
        row = self.get_row_by_slug(game_slug)
        if row:
            game_pixpuf = get_pixbuf_for_game(game_slug, self.icon_type,
                                              is_installed=is_installed)
            row[COL_ICON] = game_pixpuf
            row[COL_INSTALLED] = is_installed

    def update_all_icons(self, icon_type):
        for row in self.store:
            row[COL_ICON] = get_pixbuf_for_game(row[COL_ID], icon_type,
                                                is_installed=row[COL_INSTALLED])

    def set_icon_type(self, icon_type):
        if icon_type != self.icon_type:
            self.icon_type = icon_type
            self.update_all_icons(icon_type)
            self.emit('icons-changed', icon_type)


class GameView(object):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    selected_game = None
    current_path = None
    contextual_menu = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect('button-press-event', self.popup_contextual_menu)

    def popup_contextual_menu(self, view, event):
        """Contextual menu."""
        if event.button != 3:
            return
        try:
            view.current_path = view.get_path_at_pos(event.x, event.y)
            if view.current_path:
                if type(view) is GameGridView:
                    view.select_path(view.current_path)
                elif type(view) is GameListView:
                    view.set_cursor(view.current_path[0])
        except ValueError:
            (_, path) = view.get_selection().get_selected()
            view.current_path = path
        if view.current_path:
            game_row = self.store.get_row_by_slug(self.selected_game)
            self.contextual_menu.popup(event, game_row)


class GameListView(Gtk.TreeView, GameView):
    """Show the main list of games."""
    __gsignals__ = GameView.__gsignals__

    def __init__(self, store):
        self.store = store
        self.model = store.modelfilter.sort_new_with_model()
        super(GameListView, self).__init__(self.model)
        self.set_enable_search(False)

        # Icon
        image_cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn(title='Name')
        column.pack_start(image_cell, False)
        column.set_attributes(image_cell, pixbuf=COL_ICON)

        # Text
        default_text_cell = self.set_text_cell()
        name_cell = self.set_text_cell()
        name_cell.set_padding(5, 0)
        column.pack_start(name_cell, True)
        column.set_attributes(name_cell, text=COL_NAME)
        column.set_sort_column_id(COL_NAME)
        column.set_expand(True)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.append_column(column)
        column = self.set_column(default_text_cell, "Year", COL_YEAR)
        self.append_column(column)
        column = self.set_column(default_text_cell, "Runner", COL_RUNNER)
        self.append_column(column)

        self.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        self.connect_signals()
        self.connect('row-activated', self.on_row_activated)
        self.connect('cursor-changed', self.on_cursor_changed)

    def set_text_cell(self):
        text_cell = Gtk.CellRendererText()
        text_cell.set_padding(10, 0)
        text_cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        return text_cell

    def set_column(self, cell, header, column_id, sort_id=None):
        column = Gtk.TreeViewColumn(header, cell, text=column_id)
        column.set_sort_indicator(True)
        column.set_sort_column_id(sort_id if sort_id else column_id)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        return column

    def get_selected_game(self):
        """Return the currently selected game's slug."""
        selection = self.get_selection()
        if not selection:
            return
        model, select_iter = selection.get_selected()
        if not select_iter:
            return
        return model.get_value(select_iter, COL_ID)

    def set_selected_game(self, game_slug):
        row = self.store.get_row_by_slug(game_slug)
        if row:
            self.set_cursor(row.path)

    def on_cursor_changed(self, widget, line=None, column=None):
        self.selected_game = self.get_selected_game()
        self.emit("game-selected")

    def on_row_activated(self, widget, line=None, column=None):
        self.selected_game = self.get_selected_game()
        self.emit("game-activated")


class GameGridView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__

    def __init__(self, store):
        self.store = store
        self.model = store.modelfilter
        super(GameGridView, self).__init__(model=self.model)
        self.set_column_spacing(1)
        self.set_item_padding(1)
        self.set_spacing(1)
        self.set_row_spacing(1)
        self.set_pixbuf_column(COL_ICON)
        width = BANNER_SIZE[0] if store.icon_type == "banner" else BANNER_SMALL_SIZE[0]
        self.set_item_width(width)
        self.gridview_cell_renderer = GridViewCellRendererText(width)
        self.pack_end(self.gridview_cell_renderer, False)
        self.add_attribute(self.gridview_cell_renderer, 'text', COL_NAME)

        self.connect_signals()
        self.connect('item-activated', self.on_item_activated)
        self.connect('selection-changed', self.on_selection_changed)
        store.connect('icons-changed', self.on_icons_changed)

    def on_icons_changed(self, store, icon_type):
        width = BANNER_SIZE[0] if icon_type == "banner" else BANNER_SMALL_SIZE[0]
        self.set_item_width(width)
        self.gridview_cell_renderer.props.width = width
        self.queue_draw()

    def get_selected_game(self):
        """Return the currently selected game's slug."""
        selection = self.get_selected_items()
        if not selection:
            return
        self.current_path = selection[0]
        store = self.get_model()
        return store.get(store.get_iter(self.current_path), COL_ID)[0]

    def set_selected_game(self, game_slug):
        row = self.store.get_row_by_slug(game_slug)
        if row:
            self.select_path(row.path)

    def on_item_activated(self, view, path):
        self.selected_game = self.get_selected_game()
        self.emit("game-activated")

    def on_selection_changed(self, view):
        self.selected_game = self.get_selected_game()
        self.emit("game-selected")


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
        try:
            self.downloader = Downloader(self.url, self.dest)
        except RuntimeError as ex:
            from lutris.gui.dialogs import ErrorDialog
            ErrorDialog(ex.message)
            self.emit('cancelrequested', {})
            return
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

        self.file_chooser_dlg = Gtk.FileChooserDialog(
            title="Select folder",
            transient_for=None,
            action=action
        )

        self.file_chooser_dlg.add_buttons(
            Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        if default:
            self.file_chooser_dlg.set_current_folder(
                os.path.expanduser(default)
            )

        button = Gtk.Button()
        button.set_label("Browse...")
        button.connect('clicked', self.open_filechooser, default)
        self.add(button)

    def open_filechooser(self, widget, default):
        if default:
            self.file_chooser_dlg.set_current_folder(
                os.path.expanduser(default)
            )
        self.file_chooser_dlg.connect('response', self.select_file)
        self.file_chooser_dlg.run()

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
            target_path = dialog.get_filename()
            if target_path:
                self.file_chooser_dlg.set_current_folder(target_path)
                self.entry.set_text(reverse_expanduser(target_path))
        dialog.hide()

    def get_text(self):
        return self.entry.get_text()


class Label(Gtk.Label):
    """Standardised label for config vboxes."""
    def __init__(self, message=None):
        """Custom init of label"""
        super(Label, self).__init__(label=message)
        self.set_alignment(0.1, 0.0)
        self.set_padding(PADDING, 0)
        self.set_line_wrap(True)


class VBox(Gtk.VBox):
    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_margin_top(20)


class Dialog(Gtk.Dialog):
    def __init__(self, title=None, parent=None):
        super(Dialog, self).__init__(title=title, parent=parent, use_header_bar=True)
