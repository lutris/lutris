from gi.repository import Gdk, GObject, GLib
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.gui.views import (
    COL_ID,
    COL_SLUG,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER,
    COL_PLATFORM,
    COL_INSTALLED,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT,
)


class GameView:
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    selected_game = None
    current_path = None
    contextual_menu = None

    def connect_signals(self):
        """Signal handlers common to all views"""
        self.connect("button-press-event", self.popup_contextual_menu)
        self.connect("key-press-event", self.handle_key_press)

    def populate_games(self, games):
        """Shortcut method to the GameStore fill_store method"""
        self.game_store.fill_store(games)

    def get_row_by_id(self, game_id, filtered=False):
        store = self.game_store.modelfilter if filtered else self.game_store.store
        for model_row in store:
            if model_row[COL_ID] == int(game_id):
                return model_row

    def has_game_id(self, game_id):
        return bool(self.get_row_by_id(game_id))

    def add_game_by_id(self, game_id):
        self.game_store.add_game_by_id(game_id)

    def remove_game(self, removed_id):
        row = self.get_row_by_id(removed_id)
        if row:
            self.remove_row(row.iter)
        else:
            logger.warning("Tried to remove %s but couln't find the row", removed_id)

    def remove_row(self, model_iter):
        """Remove a game from the view."""
        store = self.game_store.store
        store.remove(model_iter)

    def set_installed(self, game):
        """Update a game row to show as installed"""
        row = self.get_row_by_id(game.id)
        if not row:
            raise ValueError("Couldn't find row for id %d (%s)" % (game.id, game))
        row[COL_RUNNER] = game.runner_name
        row[COL_PLATFORM] = ""
        self.update_image(game.id, is_installed=True)

    def set_uninstalled(self, game):
        """Update a game row to show as uninstalled"""
        row = self.get_row_by_id(game.id)
        if not row:
            raise ValueError("Couldn't find row for id %s" % game.id)
        row[COL_RUNNER] = ""
        row[COL_PLATFORM] = ""
        self.update_image(game.id, is_installed=False)

    def update_row(self, game_id, game_year, game_playtime):
        """Update game informations."""
        row = self.get_row_by_id(game_id)
        if row:
            row[COL_YEAR] = str(game_year)
            row[COL_PLAYTIME] = game_playtime
            row[COL_PLAYTIME_TEXT] = get_formatted_playtime(game_playtime)

            self.update_image(game_id, row[COL_INSTALLED])

    def update_image(self, game_id, is_installed=False):
        """Update game icon."""
        row = self.get_row_by_id(game_id)
        if row:
            game_slug = row[COL_SLUG]
            # get_pixbuf_for_game.cache_clear()
            game_pixbuf = get_pixbuf_for_game(
                game_slug, self.game_store.icon_type, is_installed
            )
            row[COL_ICON] = game_pixbuf
            row[COL_INSTALLED] = is_installed
            if "GameGridView" in self.__class__.__name__:
                GLib.idle_add(self.queue_draw)

    def popup_contextual_menu(self, view, event):
        """Contextual menu."""
        if event.button != 3:
            return
        try:
            view.current_path = view.get_path_at_pos(event.x, event.y)
            if view.current_path:
                view.select()
        except ValueError:
            (_, path) = view.get_selection().get_selected()
            view.current_path = path

        if view.current_path:
            game_row = self.get_row_by_id(self.selected_game)
            self.contextual_menu.popup(event, game_row)

    def select(self):
        """Selects the object pointed by current_path"""
        raise NotImplementedError

    def handle_key_press(self, widget, event):
        if not self.selected_game:
            return
        key = event.keyval
        if key == Gdk.KEY_Delete:
            self.emit("remove-game")
