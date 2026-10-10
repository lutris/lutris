"""The view/store lifecycle of the main window.

The window shows a grid or a list of games, and rebuilds it when the filters, the sort or the
library change. That lifecycle- which views exist, which store backs them, how concurrent
updates are discarded, and how the selection survives a rebuild- lives here, in one place.

The manager owns no widgets and reads nothing from the window directly; it talks to it through
the small GameViewHost interface below, so it can be driven by a fake host in tests.
"""

from collections.abc import Sequence
from gettext import gettext as _
from gettext import ngettext
from typing import Any, Protocol, cast

from gi.repository import GLib, Gtk

from lutris import settings
from lutris.gui.selection import retained_game_ids
from lutris.gui.view_state import GameViewState
from lutris.gui.views.grid import GameGridView
from lutris.gui.views.list import GameListView
from lutris.gui.views.store import GameStore
from lutris.util.jobs import COMPLETED_IDLE_TASK, AsyncCall, schedule_at_idle
from lutris.util.log import logger


class GameViewHost(Protocol):
    """The parts of the main window that GameViewManager relies on."""

    service: Any
    view_state: GameViewState
    search_entry: Gtk.SearchEntry
    games_stack: Gtk.Stack

    @property
    def service_media(self) -> Any: ...

    @property
    def current_view_type(self) -> str: ...

    def get_games_from_filters(self) -> list: ...
    def show_empty_label(self) -> None: ...
    def show_spinner(self) -> None: ...
    def hide_overlay(self) -> None: ...
    def update_revealer(self, games: Any = None) -> None: ...
    def update_notification(self) -> None: ...
    def update_action_state(self) -> None: ...
    def on_game_selection_changed(self, view: Any, selection: Any) -> None: ...
    def on_game_activated(self, view: Any, game_id: str) -> None: ...


class GameViewManager:
    """Owns the views, the game store and the asynchronous rebuild pipeline of a window."""

    def __init__(self, host: GameViewHost) -> None:
        self.host = host
        self.views: dict[str, Any] = {}
        self._game_store_generation = 0
        self._pending_update = COMPLETED_IDLE_TASK
        self.game_store = GameStore(host.service, host.service_media)
        self.current_view: Gtk.Widget = Gtk.Box()

    def redraw_view(self) -> None:
        """Completely reconstruct the main view."""
        host = self.host
        if not self.game_store:
            logger.error("No game store yet")
            return

        view_type = host.current_view_type
        self._ensure_view(view_type)

        scrolledwindow = cast(Gtk.ScrolledWindow, host.games_stack.get_child_by_name(view_type))
        if not scrolledwindow:
            scrolledwindow = Gtk.ScrolledWindow()
            host.games_stack.add_named(scrolledwindow, view_type)

        if not scrolledwindow.get_child():
            scrolledwindow.add(self.current_view)
            scrolledwindow.show_all()

        self.update_view_settings()
        host.games_stack.set_visible_child_name(view_type)
        host.update_action_state()
        self.update_store()

    def _ensure_view(self, view_type: str) -> None:
        """Creates the view named by 'view_type' if it does not exist yet, and makes it the
        current view. This is also what wires up the view's signals."""
        if view_type in self.views:
            self.current_view = self.views[view_type]
            return

        self.game_store = GameStore(self.host.service, self.host.service_media)
        if view_type == "grid":
            self.current_view = GameGridView(
                self.game_store, hide_text=settings.read_bool_setting("hide_text_under_icons")
            )
        else:
            self.current_view = GameListView(self.game_store)

        self.current_view.connect("game-selected", self.host.on_game_selection_changed)
        self.current_view.connect("game-activated", self.host.on_game_activated)
        self.views[view_type] = self.current_view

    def rebuild_view(self, view_type: str) -> None:
        """Discards the view named by 'view_type' and, if it is the current view, regenerates
        it. This is used to update view settings that can only be set during view construction,
        and not updated later."""
        if view_type in self.views:
            view = self.views[view_type]
            scrolledwindow = cast(Gtk.ScrolledWindow, self.host.games_stack.get_child_by_name(view_type))
            scrolledwindow.remove(view)
            del self.views[view_type]
            if self.host.current_view_type == view_type:
                self.redraw_view()
            # Because the view has hooks and such hooked up, it must be explicitly
            # destroyed to disconnect everything.
            view.destroy()

    def update_view_settings(self) -> None:
        if self.current_view and self.host.current_view_type == "grid":
            show_badges = settings.read_setting("hide_badges_on_icons") != "True"
            grid_view = cast(GameGridView, self.current_view)
            grid_view.show_badges = show_badges and not bool(self.host.view_state.values.platform)

    def update_store(self) -> None:
        """Rebuilds the game store in the background and swaps it into the current view.

        Each call gets a generation number; results from an older generation are discarded, so
        updates that overlap or race never clobber each other."""
        host = self.host
        service_id = host.view_state.values.service
        service = host.service
        service_media = host.service_media
        self._game_store_generation += 1
        generation = self._game_store_generation

        def make_game_store(games: Sequence[Any]) -> tuple[Sequence[Any], GameStore]:
            game_store = GameStore(service, service_media)
            game_store.add_preloaded_games(games, service_id)
            return games, game_store

        def on_games_ready(games: Sequence[Any], error: Exception | None) -> None:
            if generation != self._game_store_generation:
                return  # no longer applicable, we got switched again!

            if error:
                raise error  # bounce any error against the backstop

            # Since get_games_from_filters() seems to be much faster than making a GameStore,
            # we defer the spinner to here, when we know how many games we will show. If there
            # are "many" we show a spinner while the store is built.
            if not games:
                host.show_empty_label()
            elif len(games) > 512:
                host.show_spinner()

            AsyncCall(make_game_store, apply_store, games)

        def apply_store(result: tuple[Sequence[Any], GameStore], error: Exception | None) -> None:
            if generation != self._game_store_generation:
                return  # no longer applicable, we got switched again!

            if error:
                raise error  # bounce any error against the backstop

            games, game_store = result

            host.search_entry.set_placeholder_text(self._get_search_placeholder_text(games))

            for view in self.views.values():
                view.service = service

            GLib.idle_add(host.update_revealer)

            self._apply_game_store(game_store, games)

            if games:
                host.hide_overlay()
            else:
                host.show_empty_label()

            host.update_notification()

        AsyncCall(host.get_games_from_filters, on_games_ready)

    def schedule_update_store(self) -> None:
        """Requests a store rebuild at idle time; repeated requests made before it runs collapse
        into a single rebuild, so a burst of signals does not start several at once."""
        if self._pending_update.source_id is not None:
            return
        self._pending_update = schedule_at_idle(self.update_store)

    def _apply_game_store(self, game_store: GameStore, games: Sequence[Any]) -> None:
        """Swaps in a freshly built store, keeping the selection the user had for the games that
        are still shown and dropping the rest."""
        if self.game_store == game_store:
            return

        self.game_store = game_store
        view_type = self.host.current_view_type

        if view_type in self.views:
            view = self.views[view_type]
            self.current_view = view
            selected_ids = [view.get_game_id_for_path(path) for path in view.get_selected()]
            view.set_game_store(self.game_store)
            # Keep only the selected games the rebuilt view still shows; a selection pointing at
            # a filtered-out or removed game would be stale.
            retained = retained_game_ids(selected_ids, lambda game_id: view.get_path_for_game_id(game_id) is not None)
            paths = [path for path in (view.get_path_for_game_id(game_id) for game_id in retained) if path]
            view.set_selected(paths, scroll_into_view=True)

    @staticmethod
    def _get_search_placeholder_text(games: Sequence[Any]) -> str:
        if not games:
            return _("Search games")

        games_count = len(games)
        return ngettext("Search %d game", "Search %d games", games_count) % games_count
