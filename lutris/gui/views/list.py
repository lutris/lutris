"""TreeView based game list"""
from gettext import gettext as _

# Third Party Libraries
# pylint: disable=no-member
from gi.repository import Gtk, Pango

# Lutris Modules
from lutris import settings
from lutris.gui.views import (
    COL_ICON, COL_INSTALLED_AT, COL_INSTALLED_AT_TEXT, COL_LASTPLAYED, COL_LASTPLAYED_TEXT, COL_NAME, COL_PLATFORM,
    COL_PLAYTIME, COL_PLAYTIME_TEXT, COL_RUNNER_HUMAN_NAME, COL_YEAR, COLUMN_NAMES
)
from lutris.gui.views.base import GameView
from lutris.gui.views.store import sort_func


class GameListView(Gtk.TreeView, GameView):

    """Show the main list of games."""

    __gsignals__ = GameView.__gsignals__

    def __init__(self, store, service_media):
        self.game_store = store
        self.service_media = service_media
        self.model = self.game_store.store
        super().__init__(model=self.model)
        GameView.__init__(self)
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

        self.set_column(name_cell, _("Name"), COL_NAME, 200, always_visible=True)
        self.set_column(default_text_cell, _("Year"), COL_YEAR, 60)
        self.set_column(default_text_cell, _("Runner"), COL_RUNNER_HUMAN_NAME, 120)
        self.set_column(default_text_cell, _("Platform"), COL_PLATFORM, 120)
        self.set_column(default_text_cell, _("Last Played"), COL_LASTPLAYED_TEXT, 120)
        self.set_sort_with_column(COL_LASTPLAYED_TEXT, COL_LASTPLAYED)
        self.set_column(default_text_cell, _("Installed At"), COL_INSTALLED_AT_TEXT, 120)
        self.set_sort_with_column(COL_INSTALLED_AT_TEXT, COL_INSTALLED_AT)
        self.set_column(default_text_cell, _("Play Time"), COL_PLAYTIME_TEXT, 100)
        self.set_sort_with_column(COL_PLAYTIME_TEXT, COL_PLAYTIME)

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

    def set_column(self, cell, header, column_id, default_width, always_visible=False, sort_id=None):
        column = Gtk.TreeViewColumn(header, cell, markup=column_id)
        column.set_sort_indicator(True)
        column.set_sort_column_id(column_id if sort_id is None else sort_id)
        self.set_column_sort(column_id if sort_id is None else sort_id)
        column.set_resizable(True)
        column.set_reorderable(True)
        width = settings.read_setting("%s_column_width" % COLUMN_NAMES[column_id], "list view")
        is_visible = settings.read_setting("%s_visible" % COLUMN_NAMES[column_id], "list view")
        column.set_fixed_width(int(width) if width else default_width)
        column.set_visible(is_visible == "True" or always_visible if is_visible else True)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)
        column.get_button().connect('button-press-event', self.on_column_header_button_pressed)
        return column

    def set_column_sort(self, col):
        """Sort a column and fallback to sorting by name and runner."""
        model = self.get_model()
        if model:
            model.set_sort_func(col, sort_func, col)

    def set_sort_with_column(self, col, sort_col):
        """Sort a column by using another column's data"""
        self.model.set_sort_func(col, sort_func, sort_col)

    def get_selected_item(self):
        """Return the currently selected game's id."""
        selection = self.get_selection()
        if not selection:
            return None
        _model, select_iter = selection.get_selected()
        if select_iter:
            return select_iter

    def select(self):
        self.set_cursor(self.current_path[0])

    def set_selected_game(self, game_id):
        row = self.game_store.get_row_by_id(game_id, filtered=True)
        if row:
            self.set_cursor(row.path)

    def on_column_header_button_pressed(self, button, event):
        """Handles column header button press events"""
        if event.button == 3:
            menu = GameListColumnToggleMenu(self.get_columns())
            menu.popup_at_pointer(None)
            return True

    def on_row_activated(self, widget, line=None, column=None):
        """Handles double clicks"""
        selected_item = self.get_selected_item()
        if selected_item:
            selected_id = self.get_selected_id(selected_item)
        else:
            selected_id = None
        self.emit("game-activated", selected_id)

    def on_cursor_changed(self, widget, _line=None, _column=None):
        selected_item = self.get_selected_item()
        self.emit("game-selected", selected_item)

    @staticmethod
    def on_column_width_changed(col, *args):
        col_name = col.get_title()
        if col_name:
            settings.write_setting(
                col_name.replace(" ", "") + "_column_width",
                col.get_fixed_width(),
                "list view",
            )


class GameListColumnToggleMenu(Gtk.Menu):

    def __init__(self, columns):
        super().__init__()
        self.columns = columns
        self.column_map = {}
        self.create_menuitems()
        self.show_all()

    def create_menuitems(self):
        for column in self.columns:
            title = column.get_title()
            if title == "":
                continue
            checkbox = Gtk.CheckMenuItem(title)
            checkbox.set_active(column.get_visible())
            if title == _("Name"):
                checkbox.set_sensitive(False)
            else:
                checkbox.connect("toggled", self.on_toggle_column)
            self.column_map[checkbox] = column
            self.append(checkbox)

    def on_toggle_column(self, check_menu_item):
        column = self.column_map[check_menu_item]
        is_visible = check_menu_item.get_active()
        column.set_visible(is_visible)
        settings.write_setting(
            column.get_title().replace(" ", "") + "_visible",
            str(is_visible),
            "list view",
        )
