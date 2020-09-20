from gi.repository import Gdk, GObject

from lutris.database.games import get_games_by_slug
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui.views import COL_ID, COL_SLUG
from lutris.util.log import logger


class GameView:
    # pylint: disable=no-member
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (Game, )),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (Game, )),
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        self.service = None
        self.selected_game = None
        self.current_path = None
        self.contextual_menu = None

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
        model = self.get_model()
        game_slug = model.get_value(selected_item, COL_SLUG)
        game_id = model.get_value(selected_item, COL_ID)
        logger.debug("Selecting %s(%s) (Service: %s)", game_slug, game_id, self.service)
        if self.service:
            return ServiceGameCollection.get_game(self.service, game_id)
        if not self.service and game_id:
            return Game(game_id)
        pga_game = get_games_by_slug(game_slug)
        if pga_game:
            return Game(pga_game[0]["id"])

    def select(self):
        """Selects the object pointed by current_path"""
        raise NotImplementedError

    def handle_key_press(self, widget, event):  # pylint: disable=unused-argument
        if not self.selected_game:
            return
        key = event.keyval
        if key == Gdk.KEY_Delete:
            logger.debug("Emit remove-game")
            self.emit("remove-game")
