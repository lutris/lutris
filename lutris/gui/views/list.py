"""TreeView based game list - GTK 4 stub for ColumnView migration"""

from gettext import gettext as _

from gi.repository import Gdk, Gio, GObject, Gtk, Pango

from lutris import settings
from lutris.gui.views import (
    COL_ID,
    COL_INSTALLED,
    COL_INSTALLED_AT,
    COL_INSTALLED_AT_TEXT,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_MEDIA_PATHS,
    COL_NAME,
    COL_PLATFORM,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT,
    COL_RUNNER_HUMAN_NAME,
    COL_SORTNAME,
    COL_YEAR,
    COLUMN_NAMES,
)
from lutris.gui.views.base import GameView


class GameListView(Gtk.TreeView, GameView):  # type:ignore[misc]
    """Show the main list of games.

    TODO: This still uses deprecated Gtk.TreeView. Will be rewritten to use
    Gtk.ColumnView in a subsequent phase.
    """

    __gsignals__ = GameView.__gsignals__

    def __init__(self, store):
        Gtk.TreeView.__init__(self)
        GameView.__init__(self)

        # Image column
        if settings.SHOW_MEDIA:
            from lutris.gui.widgets.cellrenderers import GridViewCellRendererImage

            self.image_renderer = GridViewCellRendererImage()
            self.media_column = Gtk.TreeViewColumn(
                "", self.image_renderer, media_paths=COL_MEDIA_PATHS, is_installed=COL_INSTALLED, game_id=COL_ID
            )
            self.media_column.set_reorderable(True)
            self.media_column.set_sort_indicator(False)
            self.media_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            self.append_column(self.media_column)
        else:
            self.image_renderer = None
            self.media_column = None

        self.set_game_store(store)

        # Text columns
        default_text_cell = self.set_text_cell()
        name_cell = self.set_text_cell()
        name_cell.set_padding(5, 0)

        self.set_column(name_cell, _("Name"), COL_NAME, 200, always_visible=True, sort_id=COL_SORTNAME)
        self.set_column(default_text_cell, _("Year"), COL_YEAR, 60)
        self.set_column(default_text_cell, _("Runner"), COL_RUNNER_HUMAN_NAME, 120)
        self.set_column(default_text_cell, _("Platform"), COL_PLATFORM, 120)
        self.set_column(default_text_cell, _("Last Played"), COL_LASTPLAYED_TEXT, 120, sort_id=COL_LASTPLAYED)
        self.set_column(default_text_cell, _("Play Time"), COL_PLAYTIME_TEXT, 100, sort_id=COL_PLAYTIME)
        self.set_column(default_text_cell, _("Installed At"), COL_INSTALLED_AT_TEXT, 120, sort_id=COL_INSTALLED_AT)

        self.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.connect_signals()
        self.connect("row-activated", self.on_row_activated)
        self.get_selection().connect("changed", self.on_cursor_changed)

    def set_game_store(self, game_store):
        super().set_game_store(game_store)

        self.model = game_store.store
        self.set_model(self.model)

        if self.media_column:
            size = game_store.service_media.size
            media_width = size[0]
            self.media_column.set_fixed_width(media_width)

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
        column.set_resizable(True)
        column.set_reorderable(True)
        width = settings.read_setting("%s_column_width" % COLUMN_NAMES[column_id], section="list view")
        is_visible = settings.read_setting("%s_visible" % COLUMN_NAMES[column_id], section="list view")
        column.set_fixed_width(int(width) if width else default_width)
        column.set_visible(is_visible == "True" or always_visible if is_visible else True)
        self.append_column(column)
        column.connect("notify::width", self.on_column_width_changed)
        return column

    def get_path_at(self, x, y):
        path_at = self.get_path_at_pos(x, y)
        if path_at is None:
            return None
        path, _col, _cx, _cy = path_at
        return path

    def set_selected(self, paths, scroll_into_view=False):
        selection = self.get_selection()
        selection.unselect_all()

        for idx, path in enumerate(paths):
            selection.select_path(path)
            if scroll_into_view and idx == 0:
                self.scroll_to_cell(path, None, False, 0.0, 0.0)

    def get_selected(self):
        """Return list of all selected items"""
        selection = self.get_selection().get_selected_rows()
        if not selection:
            return None
        return selection[1]

    def get_game_id_for_path(self, path):
        iterator = self.get_model().get_iter(path)
        return self.get_model().get_value(iterator, COL_ID)

    def get_path_for_game_id(self, game_id):
        if self.game_store:
            return self.game_store.get_path_by_id(game_id)
        return None

    def set_selected_game(self, game_id):
        row = self.game_store.get_row_by_id(game_id, filtered=True)
        if row:
            self.set_cursor(row.path)

    def on_row_activated(self, widget, line=None, column=None):
        """Handles double clicks"""
        selected_id = self.get_selected_game_id()
        if selected_id:
            self.emit("game-activated", selected_id)

    def on_cursor_changed(self, widget, _line=None, _column=None):
        selected_items = self.get_selected()
        self.emit("game-selected", selected_items)

    @staticmethod
    def on_column_width_changed(col, *args):
        col_name = col.get_title()
        if col_name:
            settings.write_setting(
                col_name.replace(" ", "") + "_column_width",
                col.get_fixed_width(),
                "list view",
            )


class GameListColumnToggleMenu(Gtk.Popover):
    """Column visibility toggle menu - converted from Gtk.Menu to Gtk.Popover for GTK 4."""

    def __init__(self, columns):
        super().__init__()
        self.columns = columns
        self.column_map = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        for column in self.columns:
            title = column.get_title()
            if title == "":
                continue
            checkbox = Gtk.CheckButton(label=title)
            checkbox.set_active(column.get_visible())
            if title == _("Name"):
                checkbox.set_sensitive(False)
            else:
                checkbox.connect("toggled", self.on_toggle_column)
            self.column_map[checkbox] = column
            box.append(checkbox)

        self.set_child(box)

    def on_toggle_column(self, check_button):
        column = self.column_map[check_button]
        is_visible = check_button.get_active()
        column.set_visible(is_visible)
        settings.write_setting(
            column.get_title().replace(" ", "") + "_visible",
            str(is_visible),
            "list view",
        )
