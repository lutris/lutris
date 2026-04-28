from typing import TYPE_CHECKING

from gi.repository import Gdk, GObject, Gtk

from lutris.database.games import get_game_for_service
from lutris.database.services import ServiceGameCollection
from lutris.game import GAME_START, GAME_STARTED, GAME_STOPPED, Game
from lutris.game_actions import GameActions, get_game_actions
from lutris.gui.widgets import EMPTY_NOTIFICATION_REGISTRATION
from lutris.gui.widgets.contextual_menu import ContextualMenu
from lutris.gui.widgets.utils import MEDIA_CACHE_INVALIDATED, get_application
from lutris.util.log import logger
from lutris.util.path_cache import MISSING_GAMES


class GameView:
    # pylint: disable=no-member

    if TYPE_CHECKING:
        # GameView is a mixin always used with Gtk.Widget subclasses;
        # declare get_root so mypy can resolve it.
        def get_root(self) -> Gtk.Root | None: ...

    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    # Subclasses that paint platform/missing badges override this; the list
    # view leaves it False because badges only make sense at cover sizes.
    show_badges = False

    if TYPE_CHECKING:
        # Implemented by each concrete view; declared here so on_game_start
        # can call it via the mixin.
        def set_launching(self, game_id: str, launching: bool) -> None: ...

    def __init__(self):
        self.game_store = None
        self.service = None
        self.service_media = None
        self.cache_notification_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.missing_games_updated_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.game_start_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.game_started_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.game_stopped_registration = EMPTY_NOTIFICATION_REGISTRATION

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.cache_notification_registration = MEDIA_CACHE_INVALIDATED.register(self.on_media_cache_invalidated)
        self.missing_games_updated_registration = MISSING_GAMES.updated.register(self.on_missing_games_updated)

        click_gesture = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click_gesture.connect("pressed", self.popup_contextual_menu)
        self.add_controller(click_gesture)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.handle_key_press)
        self.add_controller(key_controller)

        self.game_start_registration = GAME_START.register(self.on_game_start)
        self.game_started_registration = GAME_STARTED.register(self.on_game_finished_launching)
        self.game_stopped_registration = GAME_STOPPED.register(self.on_game_finished_launching)

    def set_game_store(self, game_store):
        self.game_store = game_store
        self.service = game_store.service
        self.service_media = game_store.service_media

    def on_media_cache_invalidated(self):
        self.queue_draw()

    def on_missing_games_updated(self):
        if self.show_badges:
            self.queue_draw()

    def disconnect_notifications(self) -> None:
        """Unregister the NotificationSource subscriptions this view holds.

        Must be called before unparenting the view — otherwise the registrations
        keep the view alive and its callbacks continue firing on a detached widget.
        """
        self.cache_notification_registration.unregister()
        self.missing_games_updated_registration.unregister()
        self.game_start_registration.unregister()
        self.game_started_registration.unregister()
        self.game_stopped_registration.unregister()

    def popup_contextual_menu(self, gesture, _n_press, x, y):
        """Contextual menu."""
        current_path = self.get_path_at(x, y)
        if current_path is not None:
            selection = self.get_selected()
            if current_path not in selection:
                selection = [current_path]
                self.set_selected(selection)

            game_actions = self.get_game_actions_for_paths(selection)
            contextual_menu = ContextualMenu(game_actions.get_game_actions())
            contextual_menu.popup_at(self, x, y, game_actions)
            return True

    def get_selected_game_actions(self) -> GameActions:
        return self.get_game_actions_for_paths(self.get_selected())

    def get_game_actions_for_paths(self, paths) -> GameActions:
        from lutris.gui.lutriswindow import LutrisWindow  # avoid circular import at module level

        game_ids = [self.get_game_id_for_path(path) for path in paths]
        games = self._get_games_by_ids(game_ids)

        window = self.get_root()
        if not isinstance(window, LutrisWindow):
            raise TypeError("GameView must be contained in a LutrisWindow, not %s" % type(window).__name__)
        return get_game_actions(games, window=window)

    def _get_games_by_ids(self, game_ids: list[str]) -> list[Game]:
        """Resolves a list of game-ids to a list of game objects,
        looking up running games, service games and all that."""

        def _get_game_by_id(id_to_find: str) -> Game:
            application = get_application()
            return application.get_game_by_id(id_to_find) if application else Game(id_to_find)

        games = []
        for game_id in game_ids:
            if self.service:
                db_game = get_game_for_service(self.service.id, game_id)

                if db_game:
                    if db_game["id"]:
                        games.append(_get_game_by_id(db_game["id"]))
                else:
                    service_game = ServiceGameCollection.get_game(self.service.id, game_id)
                    if service_game:
                        games.append(Game.create_empty_service_game(service_game, self.service))
            elif game_id:
                games.append(_get_game_by_id(game_id))

        return games

    def get_selected_game_id(self):
        """Returns the ID of the selected game, if there is exactly one- or
        None if there is no selection or a multiple-selection."""
        selected = self.get_selected()
        if len(selected) == 1:
            return self.get_game_id_for_path(selected[0])
        return None

    def handle_key_press(self, _controller, keyval, _keycode, _state):  # pylint: disable=unused-argument
        try:
            key = keyval
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
        raise NotImplementedError()

    def get_selected(self):
        return []

    def set_selected(self, paths, scroll_into_view=False):
        raise NotImplementedError()

    def get_game_id_for_path(self, path):
        raise NotImplementedError()

    def get_path_for_game_id(self, game_id):
        raise NotImplementedError()

    def on_game_start(self, game: Game) -> None:
        """Turn on the launch-bounce animation for this game.

        Cleared by GAME_STARTED (transition to STATE_RUNNING) or GAME_STOPPED.
        The view drives the actual animation in CSS via the `.launching` class
        toggled by set_launching()."""
        self.set_launching(game.id, True)

    def on_game_finished_launching(self, game: Game) -> None:
        self.set_launching(game.id, False)
