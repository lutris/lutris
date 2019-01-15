# pylint: disable=no-member
from gi.repository import Gtk
from lutris.gui.views.base import GameView
from lutris.gui.widgets.cellrenderers import GridViewCellRendererText
from lutris.gui.widgets.utils import BANNER_SIZE, BANNER_SMALL_SIZE
from lutris.gui.views import (
    COL_ID,
    COL_NAME,
    COL_ICON,
)


class GameGridView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__

    def __init__(self, store):
        self.game_store = store
        self.model = self.game_store.modelsort
        super().__init__(model=self.model)

        self.set_column_spacing(1)
        self.set_pixbuf_column(COL_ICON)
        self.set_item_padding(1)
        self.cell_width = (
            BANNER_SIZE[0] if store.icon_type == "banner" else BANNER_SMALL_SIZE[0]
        )
        self.cell_renderer = GridViewCellRendererText(self.cell_width)
        self.pack_end(self.cell_renderer, False)
        self.add_attribute(self.cell_renderer, "markup", COL_NAME)

        self.connect_signals()
        self.connect("item-activated", self.on_item_activated)
        self.connect("selection-changed", self.on_selection_changed)
        store.connect("icons-changed", self.on_icons_changed)

    def select(self):
        self.select_path(self.current_path)

    def get_selected_game(self):
        """Return the currently selected game's id."""
        selection = self.get_selected_items()
        if not selection:
            return
        self.current_path = selection[0]
        store = self.get_model()
        return store.get(store.get_iter(self.current_path), COL_ID)[0]

    def set_selected_game(self, game_id):
        row = self.game_store.get_row_by_id(game_id)
        if row:
            self.select_path(row.path)

    def on_item_activated(self, view, path):
        self.selected_game = self.get_selected_game()
        self.emit("game-activated")

    def on_selection_changed(self, view):
        self.selected_game = self.get_selected_game()
        self.emit("game-selected")

    def on_icons_changed(self, store, icon_type):
        width = BANNER_SIZE[0] if icon_type == "banner" else BANNER_SMALL_SIZE[0]
        self.set_item_width(width)
        self.cell_renderer.props.width = width
        self.queue_draw()
