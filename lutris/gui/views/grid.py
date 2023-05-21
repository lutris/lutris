"""Grid view for the main window"""
# pylint: disable=no-member
from gi.repository import Gtk

from lutris import settings
from lutris.gui.views import COL_INSTALLED, COL_MEDIA_PATH, COL_NAME, COL_PLATFORM
from lutris.gui.views.base import GameView
from lutris.gui.widgets.cellrenderers import GridViewCellRendererImage, GridViewCellRendererText
from lutris.util.log import logger


class GameGridView(Gtk.IconView, GameView):
    __gsignals__ = GameView.__gsignals__

    min_width = 70  # Minimum width for a cell

    def __init__(self, store, hide_text=False):
        Gtk.IconView.__init__(self)
        GameView.__init__(self, store.service)

        self.set_column_spacing(6)
        self._show_badges = True

        if settings.SHOW_MEDIA:
            self.image_renderer = GridViewCellRendererImage()
            self.pack_start(self.image_renderer, False)
            self._initialize_image_renderer_attributes()
        else:
            self.image_renderer = None
        self.set_item_padding(1)
        if hide_text:
            self.text_renderer = None
        else:
            self.text_renderer = GridViewCellRendererText()
            self.pack_end(self.text_renderer, False)
            self.add_attribute(self.text_renderer, "markup", COL_NAME)

        self.set_game_store(store)

        self.connect_signals()
        self.connect("item-activated", self.on_item_activated)
        self.connect("selection-changed", self.on_selection_changed)
        self.connect("style-updated", self.on_style_updated)

    def set_game_store(self, game_store):
        self.game_store = game_store
        self.service_media = game_store.service_media
        self.model = game_store.store
        self.set_model(self.model)

        size = game_store.service_media.size

        if self.image_renderer:
            self.image_renderer.media_width = size[0]
            self.image_renderer.media_height = size[1]

        if self.text_renderer:
            cell_width = max(size[0], self.min_width)
            self.text_renderer.set_width(cell_width)

    @property
    def show_badges(self):
        return self._show_badges

    @show_badges.setter
    def show_badges(self, value):
        if self._show_badges != value:
            self._show_badges = value
            self._initialize_image_renderer_attributes()
            self.queue_draw()

    def _initialize_image_renderer_attributes(self):
        if self.image_renderer:
            self.clear_attributes(self.image_renderer)
            self.add_attribute(self.image_renderer, "media_path", COL_MEDIA_PATH)
            if self.show_badges:
                self.add_attribute(self.image_renderer, "platform", COL_PLATFORM)
            else:
                self.image_renderer.platform = None
            self.add_attribute(self.image_renderer, "is_installed", COL_INSTALLED)

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

    def on_style_updated(self, widget):
        if self.text_renderer:
            self.text_renderer.clear_caches()
