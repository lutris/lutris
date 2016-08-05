# -*- coding:Utf-8 -*-
import os

from gi.repository import Gtk, GObject, Pango, GdkPixbuf, GLib
from gi.repository.GdkPixbuf import Pixbuf

from lutris.game import Game
from lutris import pga, settings
from lutris.gui.cellrenderers import GridViewCellRendererText
from lutris.runners import import_runner, InvalidRunner
from lutris.shortcuts import desktop_launcher_exists, menu_launcher_exists
from lutris.util.log import logger
from lutris.util import datapath
from lutris.util.cache import lru_cache

DEFAULT_BANNER = os.path.join(datapath.get(), 'media/default_banner.png')
DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')
UNAVAILABLE_GAME_OVERLAY = os.path.join(datapath.get(),
                                        'media/unavailable.png')
BANNER_SIZE = (184, 69)
BANNER_SMALL_SIZE = (120, 45)
ICON_SIZE = (32, 32)
(
    COL_ID,
    COL_SLUG,
    COL_NAME,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER,
    COL_INSTALLED,
) = list(range(7))


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


@lru_cache(maxsize=6)
def get_default_icon(icon, size):
    x, y = size
    return Pixbuf.new_from_file_at_size(icon, x, y)


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


@lru_cache(maxsize=1500)
def get_pixbuf_for_game(game_slug, icon_type, is_installed):
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
        pixbuf = get_default_icon(default_icon, size)
    else:
        try:
            pixbuf = Pixbuf.new_from_file_at_size(icon_path, size[0], size[1])
        except GLib.GError:
            pixbuf = get_default_icon(default_icon, size)
    if not is_installed:
        transparent_pixbuf = get_overlay(size).copy()
        pixbuf.composite(transparent_pixbuf, 0, 0, size[0], size[1],
                         0, 0, 1, 1, GdkPixbuf.InterpType.NEAREST, 100)
        return transparent_pixbuf
    return pixbuf


class GameStore(GObject.Object):
    __gsignals__ = {
        "icons-changed": (GObject.SIGNAL_RUN_FIRST, None, (str,))
    }

    def __init__(self, games, icon_type, filter_installed):
        super(GameStore, self).__init__()
        self.games = games
        self.icon_type = icon_type
        self.filter_installed = filter_installed
        self.filter_text = None
        self.filter_runner = None

        self.store = Gtk.ListStore(int, str, str, Pixbuf, str, str, bool)
        self.store.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(self.filter_view)
        if games:
            self.fill_store(games)

    def fill_store(self, games):
        """Fill the model asynchronously and in steps."""
        loader = self._fill_store_generator(games)
        GLib.idle_add(loader.__next__)

    def _fill_store_generator(self, games, step=100):
        """Generator to fill the model in steps."""
        n = 0
        # self.freeze_child_notify()
        for game_id in games:
            self.add_game(game_id)

            # Yield to GTK main loop once in a while
            n += 1
            if (n % step) == 0:
                # self.thaw_child_notify()
                yield True
                # self.freeze_child_notify()
        # self.thaw_child_notify()
        yield False

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

    def add_game(self, game_id):
        """Add a game into the store."""
        if not game_id:
            return
        game_data = pga.get_game_by_field(game_id, 'id')
        if not game_data or 'slug' not in game_data:
            raise ValueError('Can\'t find game {} ({})'.format(
                game_id, game_data
            ))
        pixbuf = get_pixbuf_for_game(game_data['slug'], self.icon_type,
                                     game_data['installed'])
        name = game_data['name'].replace('&', "&amp;")
        self.store.append((
            game_data['id'],
            game_data['slug'],
            name,
            pixbuf,
            str(game_data['year']),
            game_data['runner'],
            game_data['installed']
        ))

    def update_all_icons(self, icon_type):
        for row in self.store:
            row[COL_ICON] = get_pixbuf_for_game(
                row[COL_SLUG], icon_type, is_installed=row[COL_INSTALLED]
            )

    def set_icon_type(self, icon_type):
        if icon_type != self.icon_type:
            self.icon_type = icon_type
            self.update_all_icons(icon_type)
            self.emit('icons-changed', icon_type)


class GameView(object):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (int,)),
    }
    selected_game = None
    current_path = None
    contextual_menu = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect('button-press-event', self.popup_contextual_menu)

    @property
    def n_games(self):
        return len(self.game_store.store)

    def get_row_by_id(self, game_id, filtered=False):
        game_row = None
        if filtered:
            store = self.game_store.modelfilter
        else:
            store = self.game_store.store
        for model_row in store:
            if model_row[COL_ID] == int(game_id):
                game_row = model_row
        return game_row

    def add_game(self, game_id):
        self.game_store.add_game(game_id)

    def remove_game(self, removed_id):
        row = self.get_row_by_id(removed_id)
        if row:
            self.remove_row(row.iter)
        else:
            logger.debug("Tried to remove %s but couln't find the row", removed_id)

    def remove_row(self, model_iter):
        """Remove a game from the view."""
        store = self.game_store.store
        store.remove(model_iter)

    def set_installed(self, game):
        """Update a game row to show as installed"""
        row = self.get_row_by_id(game.id)
        if not row:
            raise ValueError("Couldn't find row for id %d (%s)" % (game.id, game))
        row[COL_RUNNER] = game.runner_name
        self.update_image(game.id, is_installed=True)

    def set_uninstalled(self, game_id):
        """Update a game row to show as uninstalled"""
        row = self.get_row_by_id(game_id)
        if not row:
            raise ValueError("Couldn't find row for id %s" % game_id)
        row[COL_RUNNER] = ''
        self.update_image(game_id, is_installed=False)

    def update_row(self, game):
        """Update game informations.

        :param dict game: Dict holding game details
        """
        row = self.get_row_by_id(game['id'])
        if row:
            row[COL_YEAR] = str(game['year'])
            self.update_image(game['id'], row[COL_INSTALLED])

    def update_image(self, game_id, is_installed=False):
        """Update game icon."""
        row = self.get_row_by_id(game_id)
        if row:
            game_slug = row[COL_SLUG]
            get_pixbuf_for_game.cache_clear()
            game_pixpuf = get_pixbuf_for_game(game_slug,
                                              self.game_store.icon_type,
                                              is_installed)
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
            game_row = self.get_row_by_id(self.selected_game)
            self.contextual_menu.popup(event, game_row)


class GameListView(Gtk.TreeView, GameView):
    """Show the main list of games."""
    __gsignals__ = GameView.__gsignals__

    def __init__(self, store):
        self.game_store = store
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
        column.set_fixed_width(int(width) if width else 200)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        column = self.set_column(default_text_cell, "Year", COL_YEAR)
        width = settings.read_setting('year_column_width', 'list view')
        column.set_fixed_width(int(width) if width else 60)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        column = self.set_column(default_text_cell, "Runner", COL_RUNNER)
        width = settings.read_setting('runner_column_width', 'list view')
        column.set_fixed_width(int(width) if width else 100)
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
        """Return the currently selected game's id."""
        selection = self.get_selection()
        if not selection:
            return
        model, select_iter = selection.get_selected()
        if not select_iter:
            return
        return model.get_value(select_iter, COL_ID)

    def set_selected_game(self, game_id):
        row = self.get_row_by_id(game_id, filtered=True)
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

    def __init__(self, store):
        self.game_store = store
        self.model = self.game_store.modelfilter
        super(GameGridView, self).__init__(model=self.model)

        self.set_column_spacing(1)
        self.set_pixbuf_column(COL_ICON)
        self.set_item_padding(1)
        self.cell_width = (BANNER_SIZE[0] if store.icon_type == "banner"
                           else BANNER_SMALL_SIZE[0])
        self.cell_renderer = GridViewCellRendererText(self.cell_width)
        self.pack_end(self.cell_renderer, False)
        self.add_attribute(self.cell_renderer, 'markup', COL_NAME)

        self.connect_signals()
        self.connect('item-activated', self.on_item_activated)
        self.connect('selection-changed', self.on_selection_changed)
        store.connect('icons-changed', self.on_icons_changed)

    def get_selected_game(self):
        """Return the currently selected game's id."""
        selection = self.get_selected_items()
        if not selection:
            return
        self.current_path = selection[0]
        store = self.get_model()
        return store.get(store.get_iter(self.current_path), COL_ID)[0]

    def set_selected_game(self, game_id):
        row = self.get_row_by_id(game_id, filtered=True)
        if row:
            self.select_path(row.path)

    def on_item_activated(self, view, path):
        self.selected_game = self.get_selected_game()
        self.emit("game-activated")

    def on_selection_changed(self, view):
        self.selected_game = self.get_selected_game()
        self.emit("game-selected")

    def on_icons_changed(self, store, icon_type):
        width = (BANNER_SIZE[0] if icon_type == "banner"
                 else BANNER_SMALL_SIZE[0])
        self.set_item_width(width)
        self.cell_renderer.props.width = width
        self.queue_draw()


class ContextualMenu(Gtk.Menu):
    def __init__(self, main_entries):
        super(ContextualMenu, self).__init__()
        self.main_entries = main_entries

    def add_menuitems(self, entries):
        for entry in entries:
            name = entry[0]
            label = entry[1]
            action = Gtk.Action(name=name, label=label)
            action.connect('activate', entry[2])
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)

    def popup(self, event, game_row):
        game_id = game_row[COL_ID]
        game_slug = game_row[COL_SLUG]
        runner_slug = game_row[COL_RUNNER]

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Main items
        self.add_menuitems(self.main_entries)
        # Runner specific items
        runner_entries = None
        if runner_slug:
            game = Game(game_id)
            try:
                runner = import_runner(runner_slug)(game.config)
            except InvalidRunner:
                runner_entries = None
            else:
                runner_entries = runner.context_menu_entries
        if runner_entries:
            self.append(Gtk.SeparatorMenuItem())
            self.add_menuitems(runner_entries)
        self.show_all()

        # Hide some items
        is_installed = game_row[COL_INSTALLED]
        hiding_condition = {
            'add': is_installed,
            'install': is_installed,
            'install_more': not is_installed,
            'play': not is_installed,
            'configure': not is_installed,
            'desktop-shortcut': (
                not is_installed
                or desktop_launcher_exists(game_slug, game_id)
            ),
            'menu-shortcut': (
                not is_installed
                or menu_launcher_exists(game_slug, game_id)
            ),
            'rm-desktop-shortcut': (
                not is_installed
                or not desktop_launcher_exists(game_slug, game_id)
            ),
            'rm-menu-shortcut': (
                not is_installed
                or not menu_launcher_exists(game_slug, game_id)
            ),
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
