from typing import List

from gi.repository import Gdk, Gio, GObject

from lutris.database.games import get_game_for_service
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.game_actions import BaseGameActions, get_game_actions
from lutris.gui.widgets.contextual_menu import ContextualMenu
from lutris.util.log import logger


class GameView:
    # pylint: disable=no-member
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, service):
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
            contextual_menu = ContextualMenu(game_actions.get_game_actions())
            contextual_menu.popup(event, game_actions)
            return True

    def get_selected_game_actions(self) -> BaseGameActions:
        return self.get_game_actions_for_paths(self.get_selected())

    def get_game_actions_for_paths(self, paths) -> BaseGameActions:
        game_ids = []
        for path in paths:
            game_ids.append(self.get_game_id_for_path(path))
        games = self._get_games_by_ids(game_ids)
        return get_game_actions(games, window=self.get_toplevel())

    def _get_games_by_ids(self, game_ids: List[str]) -> List[Game]:
        """Resolves a list of game-ids to a list of game objects,
        looking up running games, service games and all that."""
        application = Gio.Application.get_default()

        def _get_game_by_id(id_to_find: str) -> Game:
            running = application.get_running_game_by_id(id_to_find) if application else None
            return running or Game(id_to_find)

        games = []
        for game_id in game_ids:
            if self.service:
                db_game = get_game_for_service(self.service.id, game_id)

                if db_game:
                    game = _get_game_by_id(db_game["id"])
                else:
                    db_game = ServiceGameCollection.get_game(self.service.id, game_id)
                    game = Game.create_empty_service_game(db_game, self.service)
            elif game_id:
                game = _get_game_by_id(game_id)
            else:
                continue
            games.append(game)

        return games

    def get_selected_game_id(self):
        """Returns the ID of the selected game, if there is exactly one- or
        None if there is no selection or a multiple-selection."""
        selected = self.get_selected()
        if len(selected) == 1:
            return self.get_game_id_for_path(selected[0])
        return None

    def handle_key_press(self, widget, event):  # pylint: disable=unused-argument
        try:
            key = event.keyval
            if key == Gdk.KEY_Delete:
                game_actions = self.get_selected_game_actions()
                if game_actions.is_game_removable:
                    game_actions.on_remove_game(self)
            elif key == Gdk.KEY_Break:
                game_actions = self.get_selected_game_actions()
                if game_actions.is_game_running:
                    game_actions.on_game_stop(self)
        except Exception as ex:
            logger.exception("Unable to handle key press: %s", ex)

    def get_toplevel(self):
        return None

    def get_selected(self):
        return []

    def get_game_id_for_path(self, path):
        raise NotImplementedError
