from gi.repository import Gdk, Gio, GObject

from lutris.database.games import get_game_for_service
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.game_actions import get_game_actions
from lutris.gui.views import COL_ID
from lutris.gui.widgets.contextual_menu import ContextualMenu
from lutris.util.log import logger


class GameView:
    # pylint: disable=no-member
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, service):
        self.current_path = None
        self.service = service

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect("button-press-event", self.popup_contextual_menu)
        self.connect("key-press-event", self.handle_key_press)

    def popup_contextual_menu(self, view, event):
        """Contextual menu."""
        if event.button != Gdk.BUTTON_SECONDARY:
            return
        current_path = self.get_path_at(event.x, event.y)
        if current_path:
            selection = self.get_selected()
            if current_path not in selection:
                self.set_selected(current_path)
                selection = [current_path]

            game_actions = self.get_game_actions_for_paths(selection)
            if game_actions:
                contextual_menu = ContextualMenu(game_actions.get_game_actions())
                contextual_menu.popup(event, game_actions)
                return True

    def get_selected_game_actions(self):
        return self.get_game_actions_for_paths(self.get_selected())

    def get_game_actions_for_paths(self, paths):
        game_ids = []
        for path in paths:
            iterator = self.get_model().get_iter(path)
            game_id = self.get_model().get_value(iterator, COL_ID)
            game_ids.append(game_id)
        return self.get_game_actions(game_ids)

    def get_game_actions(self, game_ids):
        games = []
        for game_id in game_ids:
            if self.service:
                db_game = get_game_for_service(self.service.id, game_id)

                if db_game:
                    game = self.get_game_by_id(db_game["id"])
                else:
                    db_game = ServiceGameCollection.get_game(self.service.id, game_id)
                    game = Game.create_empty_service_game(db_game, self.service)
            elif game_id:
                game = self.get_game_by_id(game_id)
            else:
                return None
            games.append(game)
        return get_game_actions(games, window=self.get_toplevel())

    def get_game_by_id(self, game_id):
        application = Gio.Application.get_default()
        game = application.get_running_game_by_id(game_id) if application else None
        return game or Game(game_id)

    def get_selected_game_id(self):
        """Returns the ID of the selected game, if there is exactly one- or
        None if there is no selection or a multiple-selection."""
        selected = self.get_selected()
        if len(selected) == 1:
            iterator = self.get_model().get_iter(selected[0])
            return self.get_model().get_value(iterator, COL_ID)
        return None

    def select(self):
        """Selects the object pointed by current_path"""
        raise NotImplementedError

    def handle_key_press(self, widget, event):  # pylint: disable=unused-argument
        try:
            key = event.keyval
            if key == Gdk.KEY_Delete:
                game_actions = self.get_selected_game_actions()
                if game_actions and game_actions.is_game_removable:
                    game_actions.on_remove_game(self)
            elif key == Gdk.KEY_Break:
                game_actions = self.get_selected_game_actions()
                if game_actions and game_actions.is_game_running:
                    game_actions.on_game_stop(self)
        except Exception as ex:
            logger.exception("Unable to handle key press: %s", ex)
