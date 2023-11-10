from gi.repository import Gdk, Gio, GObject, Gtk

from lutris.database.games import get_game_for_service
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.game_actions import get_game_actions
from lutris.gui.views import COL_ID
from lutris.gui.widgets.contextual_menu import ContextualMenu


class GameView:
    # pylint: disable=no-member
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (Gtk.TreeIter,)),
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
        view.current_path = view.get_path_at_pos(event.x, event.y)
        if view.current_path:
            view.select()
            model = self.get_model()
            _iter = model.get_iter(view.current_path[0])
            if not _iter:
                return
            col_id = str(model.get_value(_iter, COL_ID))

            game_actions = self.get_game_actions(col_id)
            if game_actions:
                contextual_menu = ContextualMenu(game_actions.get_game_actions())
                contextual_menu.popup(event, game_actions)

    def get_game_actions(self, game_id):
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

        return get_game_actions(game, window=self.get_toplevel())

    def get_game_by_id(self, game_id):
        application = Gio.Application.get_default()
        game = application.get_running_game_by_id(game_id) if application else None
        return game or Game(game_id)

    def get_selected_game_id(self):
        selected_item = self.get_selected_item()
        if selected_item:
            return self.get_model().get_value(selected_item, COL_ID)
        return None

    def select(self):
        """Selects the object pointed by current_path"""
        raise NotImplementedError

    def handle_key_press(self, widget, event):  # pylint: disable=unused-argument
        key = event.keyval
        if key == Gdk.KEY_Delete:
            game_id = self.get_selected_game_id()
            if game_id:
                game_actions = self.get_game_actions(game_id)
                if game_actions and game_actions.is_game_removable:
                    game_actions.on_remove_game(self)
        elif key == Gdk.KEY_Break:
            game_id = self.get_selected_game_id()
            if game_id:
                game_actions = self.get_game_actions(game_id)
                if game_actions and game_actions.is_game_running:
                    game_actions.on_game_stop(self)
