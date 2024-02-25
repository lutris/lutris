"""Store object for a list of games"""
# pylint: disable=not-an-iterable
import time

from gi.repository import GLib, GObject, Gtk

from lutris import settings
from lutris.database import sql
from lutris.database.games import get_all_installed_game_for_service, get_games
from lutris.gui.views.store_item import StoreItem
from lutris.util.strings import gtk_safe

from . import (
    COL_ID,
    COL_INSTALLED,
    COL_INSTALLED_AT,
    COL_INSTALLED_AT_TEXT,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_MEDIA_PATHS,
    COL_NAME,
    COL_PLATFORM,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT,
    COL_RUNNER,
    COL_RUNNER_HUMAN_NAME,
    COL_SLUG,
    COL_SORTNAME,
    COL_YEAR,
)


def try_lower(value):
    try:
        out = value.lower()
    except AttributeError:
        out = value
    return out


def sort_func(model, row1, row2, sort_col):
    """Sorting function for the game store"""
    value1 = model.get_value(row1, sort_col)
    value2 = model.get_value(row2, sort_col)
    if value1 is None and value2 is None:
        value1 = value2 = 0
    elif value1 is None:
        value1 = type(value2)()
    elif value2 is None:
        value2 = type(value1)()
    value1 = try_lower(value1)
    value2 = try_lower(value2)
    diff = -1 if value1 < value2 else 0 if value1 == value2 else 1
    if diff == 0:
        value1 = try_lower(model.get_value(row1, COL_SORTNAME))
        value2 = try_lower(model.get_value(row2, COL_SORTNAME))
        try:
            diff = -1 if value1 < value2 else 0 if value1 == value2 else 1
        except TypeError:
            diff = 0
    if diff == 0:
        value1 = try_lower(model.get_value(row1, COL_RUNNER_HUMAN_NAME))
        value2 = try_lower(model.get_value(row2, COL_RUNNER_HUMAN_NAME))
    try:
        return -1 if value1 < value2 else 0 if value1 == value2 else 1
    except TypeError:
        return 0


class GameStore(GObject.Object):
    def __init__(self, service, service_media):
        super().__init__()
        self.service = service
        self.service_media = service_media
        self._installed_games = []
        self._installed_games_accessed = False
        self._icon_updates = {}

        self.store = Gtk.ListStore(
            str,
            str,
            str,
            str,
            GObject.TYPE_PYOBJECT,
            str,
            str,
            str,
            str,
            int,
            str,
            bool,
            int,
            str,
            float,
            str,
        )

    @property
    def installed_game_slugs(self):
        previous_access = self._installed_games_accessed or 0
        self._installed_games_accessed = time.time()
        if self._installed_games_accessed - previous_access > 1:
            self._installed_games = [g["slug"] for g in get_games(filters={"installed": "1"})]
        return self._installed_games

    def get_row_by_slug(self, slug):
        for model_row in self.store:
            if model_row[COL_SLUG] == slug:
                return model_row

    def get_row_by_id(self, _id):
        if not _id:
            return
        for model_row in self.store:
            try:
                if model_row[COL_ID] == str(_id):
                    return model_row
            except TypeError:
                return

    def remove_game(self, _id):
        """Remove a game from the view."""
        row = self.get_row_by_id(_id)
        if row:
            self.store.remove(row.iter)

    def update(self, db_game):
        """Update game information
        Return whether a row was updated; False if the game was not already
        present.
        """
        store_item = StoreItem(db_game, self.service_media)
        row = self.get_row_by_id(store_item.id)
        if not row and "service_id" in db_game:
            row = self.get_row_by_id(db_game["service_id"])
        if not row:
            return False
        row[COL_ID] = str(store_item.id)
        row[COL_SLUG] = store_item.slug
        row[COL_NAME] = store_item.name
        row[COL_SORTNAME] = store_item.sortname if store_item.sortname else store_item.name
        row[COL_MEDIA_PATHS] = store_item.get_media_paths() if settings.SHOW_MEDIA else []
        row[COL_YEAR] = store_item.year
        row[COL_RUNNER] = store_item.runner
        row[COL_RUNNER_HUMAN_NAME] = store_item.runner_text
        row[COL_PLATFORM] = store_item.platform
        row[COL_LASTPLAYED] = store_item.lastplayed
        row[COL_LASTPLAYED_TEXT] = store_item.lastplayed_text
        row[COL_INSTALLED] = store_item.installed
        row[COL_INSTALLED_AT] = store_item.installed_at
        row[COL_INSTALLED_AT_TEXT] = store_item.installed_at_text
        row[COL_PLAYTIME] = store_item.playtime
        row[COL_PLAYTIME_TEXT] = store_item.playtime_text
        return True

    def add_game(self, db_game):
        """Add a game to the store"""
        store_item = StoreItem(db_game, self.service_media)
        self.add_item(store_item)

    def add_item(self, store_item):
        self.store.append(
            (
                store_item.id,
                store_item.slug,
                store_item.name,
                store_item.sortname if store_item.sortname else store_item.name,
                store_item.get_media_paths() if settings.SHOW_MEDIA else [],
                store_item.year,
                store_item.runner,
                store_item.runner_text,
                gtk_safe(store_item.platform),
                store_item.lastplayed,
                store_item.lastplayed_text,
                store_item.installed,
                store_item.installed_at,
                store_item.installed_at_text,
                store_item.playtime,
                store_item.playtime_text,
            )
        )

    def add_preloaded_games(self, db_games, service_id):
        """Add games to the store, but preload their installed-game data
        all at once, for faster database access. This should be used if all or almost all
        games are being loaded."""

        installed_db_games = {}
        if service_id and db_games:
            installed_db_games = get_all_installed_game_for_service(service_id)

        for db_game in db_games:
            if installed_db_games is not None and "appid" in db_game:
                appid = db_game["appid"]
                store_item = StoreItem(db_game, self.service_media)
                store_item.apply_installed_game_data(installed_db_games.get(appid))
                self.add_item(store_item)
            else:
                self.add_game(db_game)

    def on_game_updated(self, game):
        if self.service:
            db_games = sql.filtered_query(
                settings.DB_PATH,
                "service_games",
                filters=({"service": self.service_media.service, "appid": game.appid}),
            )
        else:
            db_games = sql.filtered_query(settings.DB_PATH, "games", filters=({"id": game.id}))

        for db_game in db_games:
            GLib.idle_add(self.update, db_game)
        return True
