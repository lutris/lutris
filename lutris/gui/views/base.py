from gi.repository import Gdk, GObject, Gtk

from lutris.database.games import get_game_for_service
from lutris.game import Game
from lutris.game_actions import GameActions
from lutris.gui.views import COL_ID


class GameView:
    # pylint: disable=no-member
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (Gtk.TreeIter, )),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        self.service = None  # Stores the service.id in a string
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
        view.current_path = view.get_path_at_pos(event.x, event.y)
        if view.current_path:
            view.select()
            selected_id = self.get_selected_id(self.get_model().get_iter(view.current_path))
            game_row = self.game_store.get_row_by_id(selected_id)
            game_id = None
            if self.service:
                game = get_game_for_service(self.service, game_row[COL_ID])
                if game:
                    game_id = game["id"]
            else:
                game_id = game_row[COL_ID]
            if not game_id:
                return
            game = Game(game_id)
            game_actions = GameActions()
            game_actions.set_game(game=game)

            self.contextual_menu.popup(event, game_actions)

    def get_selected_id(self, selected_item):
        return self.get_model().get_value(selected_item, COL_ID)

    def select(self):
        """Selects the object pointed by current_path"""
        raise NotImplementedError

    def handle_key_press(self, widget, event):  # pylint: disable=unused-argument
        key = event.keyval
        if key == Gdk.KEY_Delete:
            self.emit("remove-game")
