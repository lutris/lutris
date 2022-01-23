"""Store object for a list of games"""
# pylint: disable=not-an-iterable
import time

from gi.repository import GLib, GObject, Gtk
from gi.repository.GdkPixbuf import Pixbuf

from lutris import settings
from lutris.database import sql
from lutris.database.games import get_games
from lutris.gui.views.store_item import StoreItem
from lutris.gui.widgets.utils import get_pixbuf
from lutris.util.strings import gtk_safe

from . import (
    COL_ICON, COL_ID, COL_INSTALLED, COL_INSTALLED_AT, COL_INSTALLED_AT_TEXT, COL_LASTPLAYED, COL_LASTPLAYED_TEXT,
    COL_NAME, COL_PLATFORM, COL_PLAYTIME, COL_PLAYTIME_TEXT, COL_RUNNER, COL_RUNNER_HUMAN_NAME, COL_SLUG, COL_YEAR
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
        value1 = try_lower(model.get_value(row1, COL_NAME))
        value2 = try_lower(model.get_value(row2, COL_NAME))
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
    __gsignals__ = {
        "icons-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

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
            Pixbuf,
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

    def add_games(self, games):
        """Add games to the store"""
        for game in list(games):
            GLib.idle_add(self.add_game, game)

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
        """Update game informations
        Return whether a row was updated
        """
        store_item = StoreItem(db_game, self.service_media)
        row = self.get_row_by_id(store_item.id)
        if not row:
            row = self.get_row_by_id(db_game["service_id"])
        if not row:
            return False
        row[COL_ID] = str(store_item.id)
        row[COL_SLUG] = store_item.slug
        row[COL_NAME] = gtk_safe(store_item.name)
        if settings.SHOW_MEDIA:
            row[COL_ICON] = store_item.get_pixbuf()
        else:
            row[COL_ICON] = None
        row[COL_YEAR] = store_item.year
        row[COL_RUNNER] = store_item.runner
        row[COL_RUNNER_HUMAN_NAME] = gtk_safe(store_item.runner_text)
        row[COL_PLATFORM] = gtk_safe(store_item.platform)
        row[COL_LASTPLAYED] = store_item.lastplayed
        row[COL_LASTPLAYED_TEXT] = store_item.lastplayed_text
        row[COL_INSTALLED] = store_item.installed
        row[COL_INSTALLED_AT] = store_item.installed_at
        row[COL_INSTALLED_AT_TEXT] = store_item.installed_at_text
        row[COL_PLAYTIME] = store_item.playtime
        row[COL_PLAYTIME_TEXT] = store_item.playtime_text
        return True

    def add_game(self, db_game):
        """Add a PGA game to the store"""
        game = StoreItem(db_game, self.service_media)
        self.store.append(
            (
                str(game.id),
                game.slug,
                game.name,
                game.get_pixbuf() if settings.SHOW_MEDIA else None,
                game.year,
                game.runner,
                game.runner_text,
                gtk_safe(game.platform),
                game.lastplayed,
                game.lastplayed_text,
                game.installed,
                game.installed_at,
                game.installed_at_text,
                game.playtime,
                game.playtime_text,
            )
        )

    def on_game_updated(self, game):
        if self.service:
            db_games = sql.filtered_query(
                settings.PGA_DB,
                "service_games",
                filters=({
                    "service": self.service_media.service,
                    "appid": game.appid
                })
            )
        else:
            db_games = sql.filtered_query(
                settings.PGA_DB,
                "games",
                filters=({
                    "id": game.id
                })
            )

        for db_game in db_games:
            GLib.idle_add(self.update, db_game)
        return True

    def update_icons(self, icon_updates):
        """Updates the store with new icon paths keyed by slug"""
        if not settings.SHOW_MEDIA:
            return
        for slug in icon_updates:
            row = self.get_row_by_slug(slug)
            if not row:
                continue
            installed = slug in self.installed_game_slugs
            row[COL_ICON] = get_pixbuf(icon_updates[slug], self.service_media.size, is_installed=installed)
