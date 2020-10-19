"""Store object for a list of games"""
# pylint: disable=not-an-iterable
import time

from gi.repository import GLib, GObject, Gtk
from gi.repository.GdkPixbuf import Pixbuf

from lutris import settings
from lutris.database import sql
from lutris.database.games import get_games
from lutris.game import Game
from lutris.gui.views.media_loader import MediaLoader
from lutris.gui.views.store_item import StoreItem
from lutris.gui.widgets.utils import get_pixbuf, get_pixbuf_for_game
from lutris.services.base import BaseService
from lutris.util.strings import gtk_safe

from . import (
    COL_ICON, COL_ID, COL_INSTALLED, COL_INSTALLED_AT, COL_INSTALLED_AT_TEXT, COL_LASTPLAYED, COL_LASTPLAYED_TEXT,
    COL_NAME, COL_PLATFORM, COL_PLAYTIME, COL_PLAYTIME_TEXT, COL_RUNNER, COL_RUNNER_HUMAN_NAME, COL_SLUG, COL_YEAR
)

PGA_DB = settings.PGA_DB


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
        self.media_loader = MediaLoader()
        self.media_loader.connect("icon-loaded", self.on_icon_loaded)
        GObject.add_emission_hook(Game, "game-updated", self.on_game_updated)
        GObject.add_emission_hook(Game, "game-removed", self.on_game_updated)
        GObject.add_emission_hook(BaseService, "service-games-loaded", self.on_service_games_updated)

    @property
    def installed_game_slugs(self):
        previous_access = self._installed_games_accessed or 0
        self._installed_games_accessed = time.time()
        if self._installed_games_accessed - previous_access > 1:
            self._installed_games = [g["slug"] for g in get_games(filters={"installed": "1"})]
        return self._installed_games

    def load_icons(self):
        """Downloads the icons for a service"""
        media_urls = self.service_media.get_media_urls()
        self.media_loader.download_icons(media_urls, self.service_media)

    def add_games(self, games):
        """Add games to the store"""
        for game in list(games):
            GLib.idle_add(self.add_game, game)

    def get_row_by_id(self, _id):
        if not _id:
            return
        for model_row in self.store:
            try:
                if model_row[COL_ID] == _id:
                    return model_row
            except TypeError:
                return

    def remove_game(self, _id):
        """Remove a game from the view."""
        row = self.get_row_by_id(_id)
        if row:
            self.store.remove(row.iter)

    def update(self, db_game):
        """Update game informations."""
        game = StoreItem(db_game, self.service_media)
        row = self.get_row_by_id(game.id)
        if not row:
            return
        row[COL_ID] = game.id
        row[COL_SLUG] = game.slug
        row[COL_NAME] = gtk_safe(game.name)
        row[COL_ICON] = game.get_pixbuf()
        row[COL_YEAR] = game.year
        row[COL_RUNNER] = game.runner
        row[COL_RUNNER_HUMAN_NAME] = gtk_safe(game.runner_text)
        row[COL_PLATFORM] = gtk_safe(game.platform)
        row[COL_LASTPLAYED] = game.lastplayed
        row[COL_LASTPLAYED_TEXT] = game.lastplayed_text
        row[COL_INSTALLED] = game.installed
        row[COL_INSTALLED_AT] = game.installed_at
        row[COL_INSTALLED_AT_TEXT] = game.installed_at_text
        row[COL_PLAYTIME] = game.playtime
        row[COL_PLAYTIME_TEXT] = game.playtime_text

    def add_game(self, db_game):
        """Add a PGA game to the store"""
        game = StoreItem(db_game, self.service_media)
        self.store.append(
            (
                str(game.id),
                game.slug,
                game.name,
                game.get_pixbuf(),
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

    def set_service_media(self, service_media):
        """Change the icon type"""
        if service_media == self.service_media:
            return
        self.service_media = service_media
        for row in self.store:
            try:
                slug = row[COL_SLUG]
                is_installed = row[COL_INSTALLED]
                row[COL_ICON] = get_pixbuf_for_game(slug, self.service_media.size, is_installed=is_installed)
            except TypeError:
                return
        self.emit("icons-changed")

    def on_icon_loaded(self, media_loader, appid, _path, width, heigth):
        row = self.get_row_by_id(appid)
        if not row:
            return
        if width != self.service_media.size[0]:
            return
        installed = appid in self.installed_game_slugs
        row[COL_ICON] = get_pixbuf(_path, (width, heigth), is_installed=installed)

    def on_game_updated(self, game):
        if self.service:
            db_games = sql.filtered_query(PGA_DB, "service_games", filters=({
                "service": self.service_media.service,
                "appid": game.appid
            }))
        else:
            db_games = sql.filtered_query(PGA_DB, "games", filters=({
                "id": game.id
            }))

        for db_game in db_games:
            GLib.idle_add(self.update, db_game)
        return True

    def on_service_games_updated(self, game):
        """Reload icons when service games are loaded"""
        GLib.idle_add(self.load_icons)
        return True
