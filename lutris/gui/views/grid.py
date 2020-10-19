"""Grid view for the main window"""
# pylint: disable=no-member
from gi.repository import Gtk

from lutris.gui.views import COL_ICON, COL_NAME
from lutris.gui.views.base import GameView
from lutris.gui.widgets.cellrenderers import GridViewCellRendererText


class GameGridView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__

    min_width = 70  # Minimum width for a cell

    def __init__(self, store, service_media, hide_text=False):
        self.game_store = store
        self.service_media = service_media
        self.model = self.game_store.store
        super().__init__(model=self.game_store.store)
        GameView.__init__(self)

        self.service = None
        self.set_column_spacing(6)
        self.set_pixbuf_column(COL_ICON)
        self.set_item_padding(1)
        self.cell_width = (max(service_media.size[0], self.min_width))
        if hide_text:
            self.cell_renderer = None
        else:
            self.cell_renderer = GridViewCellRendererText(self.cell_width)
            self.pack_end(self.cell_renderer, False)
            self.add_attribute(self.cell_renderer, "markup", COL_NAME)

        self.connect_signals()
        self.connect("item-activated", self.on_item_activated)
        self.connect("selection-changed", self.on_selection_changed)
        store.connect("icons-changed", self.on_icons_changed)

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
        self.emit("game-activated", selected_id)

    def on_selection_changed(self, _view):
        """Handles selection changes"""
        self.emit("game-selected", self.get_selected_item())

    def on_icons_changed(self, store):
        cell_width = max(self.service_media.size[0], self.min_width)
        self.set_item_width(cell_width)
        if self.cell_renderer:
            self.cell_renderer.props.width = cell_width
        self.queue_draw()
