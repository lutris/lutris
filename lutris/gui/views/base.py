import time
from typing import List

from gi.repository import Gdk, GObject, Gtk

from lutris.database.games import get_game_for_service
from lutris.database.services import ServiceGameCollection
from lutris.game import GAME_START, Game
from lutris.game_actions import GameActions, get_game_actions
from lutris.gui.widgets import EMPTY_NOTIFICATION_REGISTRATION
from lutris.gui.widgets.contextual_menu import ContextualMenu
from lutris.gui.widgets.utils import MEDIA_CACHE_INVALIDATED, get_application
from lutris.util.jobs import schedule_repeating_at_idle
from lutris.util.log import logger
from lutris.util.path_cache import MISSING_GAMES


class GameView:
    # pylint: disable=no-member
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        self.game_store = None
        self.service = None
        self.service_media = None
        self.cache_notification_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.missing_games_updated_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.game_start_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.image_renderer = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.cache_notification_registration = MEDIA_CACHE_INVALIDATED.register(self.on_media_cache_invalidated)
        self.missing_games_updated_registration = MISSING_GAMES.updated.register(self.on_missing_games_updated)

        self.connect("destroy", self.on_destroy)
        self.connect("button-press-event", self.popup_contextual_menu)
        self.connect("key-press-event", self.handle_key_press)

        self.game_start_registration = GAME_START.register(self.on_game_start)

    def set_game_store(self, game_store):
        self.game_store = game_store
        self.service = game_store.service
        self.service_media = game_store.service_media

        size = self.service_media.size

        if self.image_renderer:
            self.image_renderer.media_width = size[0]
            self.image_renderer.media_height = size[1]
            self.image_renderer.service = self.service

    def on_media_cache_invalidated(self):
        self.queue_draw()

    def on_missing_games_updated(self):
        if self.image_renderer and self.image_renderer.show_badges:
            self.queue_draw()

    def on_destroy(self, _widget) -> None:
        self.cache_notification_registration.unregister()
        self.missing_games_updated_registration.unregister()
        self.game_start_registration.unregister()

    def popup_contextual_menu(self, view, event):
        """Contextual menu."""
        if event.button != Gdk.BUTTON_SECONDARY:
            return
        current_path = self.get_path_at(event.x, event.y)
        if current_path:
            selection = self.get_selected()
            if current_path not in selection:
                selection = [current_path]
                self.set_selected(selection)

            game_actions = self.get_game_actions_for_paths(selection)
            contextual_menu = ContextualMenu(game_actions.get_game_actions())
            contextual_menu.popup(event, game_actions)
            return True

    def get_selected_game_actions(self) -> GameActions:
        return self.get_game_actions_for_paths(self.get_selected())

    def get_game_actions_for_paths(self, paths) -> GameActions:
        game_ids = []
        for path in paths:
            game_ids.append(self.get_game_id_for_path(path))
        games = self._get_games_by_ids(game_ids)
        return get_game_actions(games, window=self.get_toplevel())

    def _get_games_by_ids(self, game_ids: List[str]) -> List[Game]:
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
                    db_game = ServiceGameCollection.get_game(self.service.id, game_id)
                    games.append(Game.create_empty_service_game(db_game, self.service))
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
        """On game start, we trigger an animation to show the game is starting; it runs at least
        one cycle, but continues until the game exits the STATE_LAUNCHING state."""

        # We animate by looking at how long the animation has been running;
        # This keeps things on track even if drawing is low or the timeout we use
        # is not quite regular.

        start_time = time.monotonic()
        cycle_time = 0.375
        max_indent = 0.1
        toplevel = self.get_toplevel()
        paused = False

        def is_modally_blocked():
            # Is there a modal dialog that is blocking our top-level parent?
            # if so we want to pause the animation.
            for w in Gtk.Window.list_toplevels():
                if w != toplevel and isinstance(w, Gtk.Dialog):
                    if w.get_modal() and w.get_transient_for() == toplevel:
                        return True

        def animate():
            nonlocal paused, start_time

            now = time.monotonic()
            elapsed = now - start_time

            if elapsed > cycle_time:
                # Check for stopping and pausing only at cycle end, so we don't do it too often,
                # and to avoid a janky looking visible snap-back to full size.
                if game.state != game.STATE_LAUNCHING:
                    if self.image_renderer.inset_game(game.id, 0.0):
                        self.queue_draw()
                    return False

                start_time = now
                paused = is_modally_blocked()

            cycle = elapsed % cycle_time

            # After 1/2 the cycle, start counting down instead of up
            if cycle > cycle_time / 2:
                cycle = cycle_time - cycle

            # scale to achieve the max_indent at cycle_time/2.
            if paused:
                fraction = 0.0
            else:
                fraction = max_indent * (cycle * 2 / cycle_time)

            if self.image_renderer.inset_game(game.id, fraction):
                self.queue_draw()

            return True  # Return True to call again after another timeout

        if self.image_renderer:
            schedule_repeating_at_idle(animate, interval_seconds=0.025)
