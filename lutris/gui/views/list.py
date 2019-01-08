# pylint: disable=no-member
from gi.repository import Gtk, Pango
from lutris import settings
from lutris.gui.views.base import GameView
from lutris.gui.views import (
    COL_ID,
    COL_NAME,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER_HUMAN_NAME,
    COL_PLATFORM,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_INSTALLED_AT,
    COL_INSTALLED_AT_TEXT,
    COL_PLAYTIME_TEXT,
    COLUMN_NAMES
)


class GameListView(Gtk.TreeView, GameView):
    """Show the main list of games."""

    __gsignals__ = GameView.__gsignals__

    def __init__(self, store):
        self.game_store = store
        self.model = self.game_store.modelsort
        super().__init__(self.model)
        self.set_rules_hint(True)

        # Icon column
        image_cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("", image_cell, pixbuf=COL_ICON)
        column.set_reorderable(True)
        column.set_sort_indicator(False)
        self.append_column(column)

        # Text columns
        default_text_cell = self.set_text_cell()
        name_cell = self.set_text_cell()
        name_cell.set_padding(5, 0)

        self.set_column(name_cell, "Name", COL_NAME, 200)
        self.set_column(default_text_cell, "Year", COL_YEAR, 60)
        self.set_column(default_text_cell, "Runner", COL_RUNNER_HUMAN_NAME, 120)
        self.set_column(default_text_cell, "Platform", COL_PLATFORM, 120)
        self.set_column(default_text_cell, "Last Played", COL_LASTPLAYED_TEXT, 120)
        self.set_sort_with_column(COL_LASTPLAYED_TEXT, COL_LASTPLAYED)
        self.set_column(default_text_cell, "Installed At", COL_INSTALLED_AT_TEXT, 120)
        self.set_sort_with_column(COL_INSTALLED_AT_TEXT, COL_INSTALLED_AT)
        self.set_column(default_text_cell, "Play Time", COL_PLAYTIME_TEXT, 100)

        self.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        self.connect_signals()
        self.connect("row-activated", self.on_row_activated)
        self.get_selection().connect("changed", self.on_cursor_changed)

    @staticmethod
    def set_text_cell():
        text_cell = Gtk.CellRendererText()
        text_cell.set_padding(10, 0)
        text_cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        return text_cell

    def set_column(self, cell, header, column_id, default_width, sort_id=None):
        column = Gtk.TreeViewColumn(header, cell, markup=column_id)
        column.set_sort_indicator(True)
        column.set_sort_column_id(column_id if sort_id is None else sort_id)
        self.set_column_sort(column_id if sort_id is None else sort_id)
        column.set_resizable(True)
        column.set_reorderable(True)
        width = settings.read_setting(
            "%s_column_width" % COLUMN_NAMES[column_id], "list view"
        )
        column.set_fixed_width(int(width) if width else default_width)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)
        return column

    def set_column_sort(self, col):
        """Sort a column and fallback to sorting by name and runner."""

        def sort_func(model, row1, row2, user_data):
            v1 = model.get_value(row1, col)
            v2 = model.get_value(row2, col)
            diff = -1 if v1 < v2 else 0 if v1 == v2 else 1
            if diff is 0:
                v1 = model.get_value(row1, COL_NAME)
                v2 = model.get_value(row2, COL_NAME)
                diff = -1 if v1 < v2 else 0 if v1 == v2 else 1
            if diff is 0:
                v1 = model.get_value(row1, COL_RUNNER_HUMAN_NAME)
                v2 = model.get_value(row2, COL_RUNNER_HUMAN_NAME)
                diff = -1 if v1 < v2 else 0 if v1 == v2 else 1
            return diff

        self.model.set_sort_func(col, sort_func)

    def set_sort_with_column(self, col, sort_col):
        """Set to sort a column by using another column"""

        def sort_func(model, row1, row2, _user_data):
            value1 = model.get_value(row1, sort_col)
            value2 = model.get_value(row2, sort_col)
            return -1 if value1 < value2 else 0 if value1 == value2 else 1

        self.model.set_sort_func(col, sort_func)

    def get_selected_game(self):
        """Return the currently selected game's id."""
        selection = self.get_selection()
        if not selection:
            return None
        model, select_iter = selection.get_selected()
        if not select_iter:
            return None
        return model.get_value(select_iter, COL_ID)

    def select(self):
        self.set_cursor(self.current_path[0])

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

    @staticmethod
    def on_column_width_changed(col, *args):
        col_name = col.get_title()
        if col_name:
            settings.write_setting(
                col_name.replace(" ", "") + "_column_width",
                col.get_fixed_width(),
                "list view",
            )
