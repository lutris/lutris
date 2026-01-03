"""Grid view for the main window"""

# pylint: disable=no-member
from gi.repository import Gtk

from lutris import settings
from lutris.gui.views import COL_ID, COL_INSTALLED, COL_MEDIA_PATHS, COL_NAME, COL_PLATFORM
from lutris.gui.views.base import GameView
from lutris.gui.widgets.cellrenderers import GridViewCellRendererImage, GridViewCellRendererText
from lutris.util.log import logger


class GameGridView(Gtk.IconView, GameView):  # type:ignore[misc]
    __gsignals__ = GameView.__gsignals__

    min_width = 70  # Minimum width for a cell

    def __init__(self, store, hide_text=False):
        Gtk.IconView.__init__(self)
        GameView.__init__(self)

        Gtk.IconView.set_selection_mode(self, Gtk.SelectionMode.MULTIPLE)

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
        super().set_game_store(game_store)
        self.model = game_store.store
        self.set_model(self.model)

        if self.text_renderer:
            size = game_store.service_media.size
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
            self.image_renderer.show_badges = self.show_badges
            self.clear_attributes(self.image_renderer)
            self.add_attribute(self.image_renderer, "game_id", COL_ID)
            self.add_attribute(self.image_renderer, "media_paths", COL_MEDIA_PATHS)
            self.add_attribute(self.image_renderer, "platform", COL_PLATFORM)
            self.add_attribute(self.image_renderer, "is_installed", COL_INSTALLED)

    def get_path_at(self, x, y):
        return self.get_path_at_pos(x, y)

    def set_selected(self, paths, scroll_into_view=False):
        self.unselect_all()

        for idx, path in enumerate(paths):
            self.select_path(path)
            if scroll_into_view and idx == 0:
                self.scroll_to_path(path, False, 0.0, 0.0)

    def get_selected(self):
        """Return list of all selected items"""
        return self.get_selected_items()

    def get_game_id_for_path(self, path):
        iterator = self.get_model().get_iter(path)
        return self.get_model().get_value(iterator, COL_ID)

    def get_path_for_game_id(self, game_id):
        path_found = None

        def check_path(model, path, iterator):
            nonlocal path_found
            row_id = model.get_value(iterator, COL_ID)
            if game_id == row_id:
                path_found = path
                return True  # stop iteration

        self.get_model().foreach(check_path)
        return path_found

    def on_item_activated(self, _view, _path):
        """Handles double clicks"""
        selected_id = self.get_selected_game_id()
        if selected_id:
            logger.debug("Item activated: %s", selected_id)
            self.emit("game-activated", selected_id)

    def on_selection_changed(self, _view):
        """Handles selection changes"""
        selected_items = self.get_selected()
        self.emit("game-selected", selected_items)

    def on_style_updated(self, widget):
        if self.text_renderer:
            self.text_renderer.clear_caches()
