"""Grid view for the main window"""
# pylint: disable=no-member
from gi.repository import Gtk

from lutris.gui.views import COL_ICON, COL_NAME
from lutris.gui.views.base import GameView
from lutris.gui.widgets.cellrenderers import GridViewCellRendererText
from lutris.util.log import logger


class GameGridView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__

    min_width = 70  # Minimum width for a cell

    def __init__(self, store, hide_text=False):
        Gtk.IconView.__init__(self)
        GameView.__init__(self, store.service)

        self.set_column_spacing(6)
        self.set_pixbuf_column(COL_ICON)
        self.set_item_padding(1)
        if hide_text:
            self.cell_renderer = None
        else:
            self.cell_renderer = GridViewCellRendererText()
            self.pack_end(self.cell_renderer, False)
            self.add_attribute(self.cell_renderer, "markup", COL_NAME)

        self.set_game_store(store)

        self.connect_signals()
        self.connect("item-activated", self.on_item_activated)
        self.connect("selection-changed", self.on_selection_changed)

    def set_game_store(self, game_store):
        self.game_store = game_store
        self.service_media = game_store.service_media
        self.model = game_store.store
        self.set_model(self.model)

        if self.cell_renderer:
            cell_width = max(game_store.service_media.size[0], self.min_width)
            self.cell_renderer.set_width(cell_width)

    def select(self):
        self.select_path(self.current_path)

    def get_selected_item(self):
        """Return the currently selected game's id."""
        selection = self.get_selected_items()
        if not selection:
            return
        self.current_path = selection[0]
        return self.get_model().get_iter(self.current_path)

    def on_item_activated(self, _view, _path):
        """Handles double clicks"""
        selected_item = self.get_selected_item()
        if selected_item:
            selected_id = self.get_selected_id(selected_item)
        else:
            selected_id = None
        logger.debug("Item activated: %s", selected_id)
        self.emit("game-activated", selected_id)

    def on_selection_changed(self, _view):
        """Handles selection changes"""
        selected_items = self.get_selected_item()
        if selected_items:
            self.emit("game-selected", selected_items)
