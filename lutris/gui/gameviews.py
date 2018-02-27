# -*- coding: utf-8 -*-

import time

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf

from lutris import pga
from lutris import runners
from lutris import settings
from lutris.game import Game

from lutris.gui.widgets.cellrenderers import GridViewCellRendererText
from lutris.gui.widgets.utils import get_pixbuf_for_game, BANNER_SIZE, BANNER_SMALL_SIZE

from lutris.services import xdg
from lutris.util.log import logger

(
    COL_ID,
    COL_SLUG,
    COL_NAME,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER,
    COL_RUNNER_HUMAN_NAME,
    COL_PLATFORM,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_INSTALLED,
) = list(range(11))

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
        self.filter_platform = None
        self.runner_names = {}

        self.store = Gtk.ListStore(int, str, str, Pixbuf, str, str, str, str, int, str, bool)
        self.store.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(self.filter_view)
        if games:
            self.fill_store(games)

    def get_ids(self):
        return [row[COL_ID] for row in self.store]

    def fill_store(self, games):
        """Fill the model asynchronously and in steps.

        Each iteration on `loader` adds a batch of games to the model as a low
        priority operation so they get displayed before adding the next batch.
        This is an optimization to avoid having to wait for all games to be
        loaded in the model before the list is drawn on the window.
        """
        loader = self._fill_store_generator(games)
        GLib.idle_add(loader.__next__)

    def _fill_store_generator(self, games, batch=100):
        """Generator to fill the model in batches."""
        n = 0
        for game in games:
            self.add_game(game)
            # Yield to GTK main loop once in a while
            n += 1
            if (n % batch) == 0:
                # Returning True to GLib.idle_add makes it run the callback
                # again. (Yeah, the GTK doc isn't clear about this feature :)
                yield True
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
        if self.filter_platform:
            platform = model.get_value(_iter, COL_PLATFORM)
            if platform != self.filter_platform:
                return False
        return True

    def add_game_by_id(self, game_id):
        """Add a game into the store."""
        if not game_id:
            return
        game = pga.get_game_by_field(game_id, 'id')
        if not game or 'slug' not in game:
            raise ValueError('Can\'t find game {} ({})'.format(
                game_id, game
            ))
        self.add_game(game)

    def add_game(self, game):
        name = game['name'].replace('&', "&amp;")
        runner = None
        platform = ''
        runner_name = game['runner']
        runner_human_name = ''
        if runner_name:
            game_inst = Game(game['id'])
            if not game_inst.is_installed:
                return
            if runner_name in self.runner_names:
                runner_human_name = self.runner_names[runner_name]
            else:
                try:
                    runner = runners.import_runner(runner_name)
                except runners.InvalidRunner:
                    game['installed'] = False
                else:
                    runner_human_name = runner.human_name
                    self.runner_names[runner_name] = runner_human_name
            platform = game_inst.platform

        lastplayed = ''
        if game['lastplayed']:
            lastplayed = time.strftime("%c", time.localtime(game['lastplayed']))

        pixbuf = get_pixbuf_for_game(game['slug'], self.icon_type,
                                     game['installed'])
        self.store.append((
            game['id'],
            game['slug'],
            name,
            pixbuf,
            str(game['year'] or ''),
            runner_name,
            runner_human_name,
            platform,
            game['lastplayed'],
            lastplayed,
            game['installed']
        ))

    def set_icon_type(self, icon_type):
        if icon_type != self.icon_type:
            self.icon_type = icon_type
            for row in self.store:
                row[COL_ICON] = get_pixbuf_for_game(
                    row[COL_SLUG], icon_type, is_installed=row[COL_INSTALLED]
                )
            self.emit('icons-changed', icon_type)  # Obsolete, only for GridView


class GameView(object):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    selected_game = None
    current_path = None
    contextual_menu = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect('button-press-event', self.popup_contextual_menu)
        self.connect('key-press-event', self.handle_key_press)

    def populate_games(self, games):
        """Shortcut method to the GameStore fill_store method"""
        self.game_store.fill_store(games)

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

    def has_game_id(self, game_id):
        return bool(self.get_row_by_id(game_id))

    def add_game_by_id(self, game_id):
        self.game_store.add_game_by_id(game_id)

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
        row[COL_PLATFORM] = ''
        self.update_image(game.id, is_installed=True)

    def set_uninstalled(self, game):
        """Update a game row to show as uninstalled"""
        row = self.get_row_by_id(game.id)
        if not row:
            raise ValueError("Couldn't find row for id %s" % game.id)
        row[COL_RUNNER] = ''
        row[COL_PLATFORM] = ''
        self.update_image(game.id, is_installed=False)

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
            # get_pixbuf_for_game.cache_clear()
            game_pixbuf = get_pixbuf_for_game(game_slug,
                                              self.game_store.icon_type,
                                              is_installed)
            row[COL_ICON] = game_pixbuf
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

    def handle_key_press(self, widget, event):
        if not self.selected_game:
            return
        key = event.keyval
        if key == Gdk.KEY_Delete:
            self.emit("remove-game")


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

        column = self.set_column(default_text_cell, "Runner", COL_RUNNER_HUMAN_NAME)
        width = settings.read_setting('runner_column_width', 'list view')
        column.set_fixed_width(int(width) if width else 120)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        column = self.set_column(default_text_cell, "Platform", COL_PLATFORM)
        width = settings.read_setting('platform_column_width', 'list view')
        column.set_fixed_width(int(width) if width else 120)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        column = self.set_column(default_text_cell, "Last played", COL_LASTPLAYED_TEXT)
        self.set_sort_with_column(COL_LASTPLAYED_TEXT, COL_LASTPLAYED)
        width = settings.read_setting('lastplayed_column_width', 'list view')
        column.set_fixed_width(int(width) if width else 120)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)

        self.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        self.connect_signals()
        self.connect('row-activated', self.on_row_activated)
        self.get_selection().connect('changed', self.on_cursor_changed)

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

    def set_sort_with_column(self, col, sort_col):
        """Set to sort a column by using another column.
        """

        def sort_func(model, row1, row2, user_data):
            v1 = model.get_value(row1, sort_col)
            v2 = model.get_value(row2, sort_col)
            return -1 if v1 < v2 else 0 if v1 == v2 else 1

        self.model.set_sort_func(col, sort_func)

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
            settings.write_setting(col_name.replace(' ', '') + '_column_width',
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

    def popup(self, event, game_row=None, game=None):
        if game_row:
            game_id = game_row[COL_ID]
            game_slug = game_row[COL_SLUG]
            runner_slug = game_row[COL_RUNNER]
            is_installed = game_row[COL_INSTALLED]
        elif game:
            game_id = game.id
            game_slug = game.slug
            runner_slug = game.runner_name
            is_installed = game.is_installed

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Main items
        self.add_menuitems(self.main_entries)
        # Runner specific items
        runner_entries = None
        if runner_slug:
            game = game or Game(game_id)
            try:
                runner = runners.import_runner(runner_slug)(game.config)
            except runners.InvalidRunner:
                runner_entries = None
            else:
                runner_entries = runner.context_menu_entries
        if runner_entries:
            self.append(Gtk.SeparatorMenuItem())
            self.add_menuitems(runner_entries)
        self.show_all()

        # Hide some items
        hiding_condition = {
            'add': is_installed,
            'install': is_installed,
            'install_more': not is_installed,
            'play': not is_installed,
            'configure': not is_installed,
            'desktop-shortcut': (
                not is_installed or
                xdg.desktop_launcher_exists(game_slug, game_id)
            ),
            'menu-shortcut': (
                not is_installed or
                xdg.menu_launcher_exists(game_slug, game_id)
            ),
            'rm-desktop-shortcut': (
                not is_installed or
                not xdg.desktop_launcher_exists(game_slug, game_id)
            ),
            'rm-menu-shortcut': (
                not is_installed or
                not xdg.menu_launcher_exists(game_slug, game_id)
            ),
            'browse': not is_installed or runner_slug == 'browser',
        }
        for menuitem in self.get_children():
            if type(menuitem) is not Gtk.ImageMenuItem:
                continue
            action = menuitem.action_id
            visible = not hiding_condition.get(action)
            menuitem.set_visible(visible)

        super(ContextualMenu, self).popup(None, None, None, None,
                                          event.button, event.time)
