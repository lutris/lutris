# Third Party Libraries
from gi.repository import Gdk, GObject

# Lutris Modules
from lutris import pga
from lutris.game import Game
from lutris.gui.views import COL_ID, COL_INSTALLED, COL_NAME, COL_SLUG
from lutris.util.log import logger


class GameView:
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (Game, )),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (Game, )),
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    selected_game = None
    current_path = None
    contextual_menu = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect("button-press-event", self.popup_contextual_menu)
        self.connect("key-press-event", self.handle_key_press)

    def popup_contextual_menu(self, view, event):
        """Contextual menu."""
        if event.button != 3:
            return
        try:
            view.current_path = view.get_path_at_pos(event.x, event.y)
            if view.current_path:
                view.select()
                game_row = self.game_store.get_row_by_id(self.selected_game.id)
                self.contextual_menu.popup(event, game_row)
        except ValueError as ex:
            logger.error("Failed to read path: %s", ex)

    def get_selected_game(self, selected_item):
        selected_game = None
        model = self.get_model()
        game_id = model.get_value(selected_item, COL_ID)
        game_slug = model.get_value(selected_item, COL_SLUG)
        pga_game = pga.get_games_by_slug(game_slug)
        if game_id > 0:
            selected_game = Game(game_id)
        elif pga_game:
            selected_game = Game(pga_game[0]["id"])
        else:
            selected_game = Game(game_id)
            selected_game.id = game_id
            selected_game.slug = game_slug
            selected_game.name = model.get_value(selected_item, COL_NAME)
            selected_game.installed = model.get_value(selected_item, COL_INSTALLED)
        return selected_game

    def select(self):
        """Selects the object pointed by current_path"""
        raise NotImplementedError

    def handle_key_press(self, widget, event):  # pylint: disable=unused-argument
        if not self.selected_game:
            return
        key = event.keyval
        if key == Gdk.KEY_Delete:
            self.emit("remove-game")
