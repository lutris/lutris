# -*- coding:Utf-8 -*-
"""Misc widgets used in the GUI."""
import os

from gi.repository import Gtk, GObject, Pango, GdkPixbuf, GLib
from gi.repository.GdkPixbuf import Pixbuf

from lutris import settings
from lutris.config import LutrisConfig
from lutris.gui.cellrenderers import GridViewCellRendererText
from lutris.downloader import Downloader
from lutris.runners import import_runner
from lutris.shortcuts import desktop_launcher_exists, menu_launcher_exists
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


def sort_func(store, a_iter, b_iter, _user_data):
    """Default sort function."""
    a_name = store.get(a_iter, COL_NAME)
    b_name = store.get(b_iter, COL_NAME)

    if a_name > b_name:
        return 1
    elif a_name < b_name:
        return -1
    else:
        return 0


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
        icon_path = default_icon
    try:
        pixbuf = Pixbuf.new_from_file_at_size(icon_path, size[0], size[1])
    except GLib.GError:
        pixbuf = Pixbuf.new_from_file_at_size(default_icon, size[0], size[1])
    if not is_installed:
        transparent_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            UNAVAILABLE_GAME_OVERLAY, size[0], size[1]
        )
        transparent_pixbuf = transparent_pixbuf.scale_simple(
            size[0], size[1], GdkPixbuf.InterpType.NEAREST
        )
        pixbuf.composite(transparent_pixbuf, 0, 0, size[0], size[1],
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf


class ContextualMenu(Gtk.Menu):
    def __init__(self, main_entries):
        super(ContextualMenu, self).__init__()
        self.main_entries = main_entries

    def add_menuitems(self, entries):
        for entry in entries:
            name = entry[0]
            label = entry[1]
            action = Gtk.Action(name=name, label=label,
                                tooltip=None, stock_id=None)
            action.connect('activate', entry[2])
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)

    def popup(self, event, game_row):
        game_slug = game_row[COL_ID]
        runner_slug = game_row[COL_RUNNER]

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Main items
        self.add_menuitems(self.main_entries)
        # Runner specific items
        runner_entries = None
        if runner_slug:
            game_config = LutrisConfig(runner_slug=runner_slug,
                                       game_slug=game_slug)
            runner = import_runner(runner_slug)(game_config)
            runner_entries = runner.context_menu_entries
        if runner_entries:
            self.append(Gtk.SeparatorMenuItem())
            self.add_menuitems(runner_entries)
        self.show_all()

        # Hide some items
        is_installed = game_row[COL_INSTALLED]
        hiding_condition = {
            'add': is_installed,
            'play': not is_installed,
            'configure': not is_installed,
            'desktop-shortcut': (not is_installed
                                 or desktop_launcher_exists(game_slug)),
            'menu-shortcut': (not is_installed
                              or menu_launcher_exists(game_slug)),
            'rm-desktop-shortcut': (not is_installed
                                    or not desktop_launcher_exists(game_slug)),
            'rm-menu-shortcut': (not is_installed
                                 or not menu_launcher_exists(game_slug)),
            'browse': not is_installed or game_row[COL_RUNNER] == 'browser',
        }
        for menuitem in self.get_children():
            if type(menuitem) is not Gtk.ImageMenuItem:
                continue
            action = menuitem.action_id
            visible = not hiding_condition.get(action)
            menuitem.set_visible(visible)

        super(ContextualMenu, self).popup(None, None, None, None,
                                          event.button, event.time)


class GameStore(object):

    def __init__(self, games, filter_text='', filter_runner='',
                 icon_type=None):
        self.filter_text = filter_text
        self.filter_runner = filter_runner
        self.icon_type = icon_type
        self.store = Gtk.ListStore(str, str, Pixbuf, str, str, bool)
        self.store.set_default_sort_func(sort_func)
        self.store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)
        self.fill_store(games)
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(self.filter_view)

    def filter_view(self, model, _iter, filter_data=None):
        """Filter the game list."""
        name = model.get_value(_iter, COL_NAME)
        runner = model.get_value(_iter, COL_RUNNER)
        if self.filter_text:
            name_matches = self.filter_text.lower() in name.lower()
        else:
            name_matches = True
        if self.filter_runner:
            runner_matches = self.filter_runner == runner
        else:
            runner_matches = True
        return name_matches and runner_matches

    def fill_store(self, games):
        self.store.clear()
        for game in games:
            self.add_game(game)

    def add_game(self, game):
        """Add a game into the store."""
        if not game.name:
            return
        pixbuf = get_pixbuf_for_game(game.slug, self.icon_type,
                                     is_installed=game.is_installed)
        name = game.name.replace('&', "&amp;")
        self.store.append(
            (game.slug, name, pixbuf, str(game.year), game.runner_name,
             game.is_installed)
        )


class GameView(object):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "filter-updated": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    selected_game = None
    current_path = None
    contextual_menu = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect('filter-updated', self.update_filter)
        self.connect('button-press-event', self.popup_contextual_menu)

    @property
    def n_games(self):
        return len(self.game_store.store)

    def get_row_by_slug(self, game_slug):
        game_row = None
        for model_row in self.game_store.store:
            if model_row[COL_ID] == game_slug:
                game_row = model_row
        return game_row

    def add_game(self, game):
        self.game_store.add_game(game)

    def remove_game(self, removed_id):
        row = self.get_row_by_slug(removed_id)
        if row:
            self.remove_row(row.iter)

    def remove_row(self, model_iter):
        """Remove a game from the view."""
        store = self.game_store.store
        store.remove(model_iter)

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

    def update_filter(self, widget):
        self.game_store.modelfilter.refilter()

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
            if type(self) is GameGridView:
                GLib.idle_add(self.queue_draw)

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
            game_row = self.get_row_by_slug(self.selected_game)
            self.contextual_menu.popup(event, game_row)


class GameListView(Gtk.TreeView, GameView):
    """Show the main list of games."""
    __gsignals__ = GameView.__gsignals__

    def __init__(self, games, filter_text='', filter_runner='',
                 icon_type=None):
        self.icon_type = icon_type
        self.game_store = GameStore(games, icon_type=icon_type,
                                    filter_text=filter_text,
                                    filter_runner=filter_runner)
        self.model = self.game_store.modelfilter.sort_new_with_model()
        super(GameListView, self).__init__(self.model)
        self.set_rules_hint(True)

        # Icon column
        image_cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("", image_cell, pixbuf=COL_ICON)
        column.set_reorderable(True)
        self.append_column(column)

        # Text columns
        default_text_cell = self.set_text_cell()
        name_cell = self.set_text_cell()
        name_cell.set_padding(5, 0)
        column = self.set_column(name_cell, "Name", COL_NAME)
        width = settings.read_setting('name_column_width', 'list view')
        column.set_fixed_width(int(width) or 200)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        column = self.set_column(default_text_cell, "Year", COL_YEAR)
        width = settings.read_setting('year_column_width', 'list view')
        column.set_fixed_width(int(width) or 60)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        column = self.set_column(default_text_cell, "Runner", COL_RUNNER)
        width = settings.read_setting('runner_column_width', 'list view')
        column.set_fixed_width(int(width) or 100)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        self.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        self.connect_signals()
        self.connect('row-activated', self.on_row_activated)
        self.connect('cursor-changed', self.on_cursor_changed)

    def set_text_cell(self):
        text_cell = Gtk.CellRendererText()
        text_cell.set_padding(10, 0)
        text_cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        return text_cell

    def set_column(self, cell, header, column_id):
        column = Gtk.TreeViewColumn(header, cell, markup=column_id)
        column.set_sort_indicator(True)
        column.set_sort_column_id(column_id)
        column.set_resizable(True)
        column.set_reorderable(True)
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
        row = self.get_row_by_slug(game_slug)
        if row:
            self.set_cursor(row.path)

    def on_cursor_changed(self, widget, line=None, column=None):
        self.selected_game = self.get_selected_game()
        self.emit("game-selected")

    def on_row_activated(self, widget, line=None, column=None):
        self.selected_game = self.get_selected_game()
        self.emit("game-activated")

    def on_column_width_changed(self, col, *args):
        col_name = col.get_title()
        if col_name:
            settings.write_setting(col_name + '_column_width',
                                   col.get_fixed_width(), 'list view')


class GameGridView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__
    icon_padding = 1

    def __init__(self, games, filter_text='', filter_runner='',
                 icon_type=None):
        self.icon_type = icon_type
        self.game_store = GameStore(games, icon_type=icon_type,
                                    filter_text=filter_text,
                                    filter_runner=filter_runner)
        self.model = self.game_store.modelfilter
        super(GameGridView, self).__init__(model=self.model)
        self.set_columns(1)
        self.set_column_spacing(1)
        self.set_pixbuf_column(COL_ICON)
        self.cell_width = BANNER_SIZE[0] if icon_type == "banner" \
            else BANNER_SMALL_SIZE[0]
        cell_renderer = GridViewCellRendererText(width=self.cell_width)
        self.pack_end(cell_renderer, False)
        self.add_attribute(cell_renderer, 'markup', COL_NAME)
        self.set_item_padding(self.icon_padding)

        self.connect_signals()
        self.connect('item-activated', self.on_item_activated)
        self.connect('selection-changed', self.on_selection_changed)
        self.connect('size-allocate', self.on_size_allocate)

    def set_fluid_columns(self, width):
        cell_width = self.cell_width + self.icon_padding * 2
        nb_columns = (width / cell_width)
        self.set_columns(nb_columns)

    def on_size_allocate(self, widget, rect):
        """Recalculate the colum spacing based on total widget width."""
        width = self.get_parent().get_allocated_width()
        self.set_fluid_columns(width - 20)
        self.do_size_allocate(widget, rect)

    def get_selected_game(self):
        """Return the currently selected game's slug."""
        selection = self.get_selected_items()
        if not selection:
            return
        self.current_path = selection[0]
        store = self.get_model()
        return store.get(store.get_iter(self.current_path), COL_ID)[0]

    def set_selected_game(self, game_slug):
        row = self.get_row_by_slug(game_slug)
        if row:
            self.select_path(row.path)

    def on_item_activated(self, view, path):
        self.selected_game = self.get_selected_game()
        self.emit("game-activated")

    def on_selection_changed(self, view):
        self.selected_game = self.get_selected_game()
        self.emit("game-selected")


class DownloadProgressBox(Gtk.VBox):
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
        self.url = params['url']
        self.dest = params['dest']
        title = params.get('title', "Downloading {}".format(self.url))

        self.main_label = Gtk.Label(title)
        self.main_label.set_alignment(0, 0)
        self.main_label.set_property('wrap', True)
        self.main_label.set_margin_bottom(10)
        self.main_label.set_selectable(True)
        self.pack_start(self.main_label, True, True, 0)

        progress_box = Gtk.Box()

        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_margin_bottom(10)
        self.progressbar.set_margin_right(10)
        progress_box.pack_start(self.progressbar, True, True, 0)

        self.cancel_button = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        self.cancel_button.connect('clicked', self.cancel)
        if not cancelable:
            self.cancel_button.set_sensitive(False)
        progress_box.pack_end(self.cancel_button, False, False, 0)

        self.pack_start(progress_box, False, False, 0)

        self.progress_label = Gtk.Label()
        self.progress_label.set_alignment(0, 0)
        self.pack_start(self.progress_label, True, True, 0)

        self.show_all()

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
            self.set_text("Download cancelled")
            self.emit('cancelrequested', {})
            return False
        self.progressbar.set_fraction(progress)
        megabytes = 1024 * 1024
        progress_text = (
            "%0.2f / %0.2fMB (%0.2fMB/s), %d seconds remaining" % (
                float(self.downloader.downloaded_bytes) / megabytes,
                float(self.downloader.total_bytes) / megabytes,
                float(self.downloader.speed) / megabytes,
                self.downloader.time_remaining
            )
        )
        self.set_text(progress_text)
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

    def set_text(self, text):
        markup = u"<span size='10000'>{}</span>".format(text)
        self.progress_label.set_markup(markup)


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
    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        super(Dialog, self).__init__(title, parent, flags, buttons)
        self.set_border_width(10)
        self.set_destroy_with_parent(True)
