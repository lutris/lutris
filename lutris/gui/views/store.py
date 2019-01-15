"""Store object for a list of games"""
from gi.repository import Gtk, GObject, GLib
from gi.repository.GdkPixbuf import Pixbuf
from lutris import pga
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.util.resources import get_icon_path, download_media
from lutris.util.log import logger
from lutris.util import system
from lutris import api
from lutris.util.jobs import AsyncCall
from lutris.gui.views.pga_game import PgaGame
from . import (
    COL_ID,
    COL_SLUG,
    COL_NAME,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER,
    COL_RUNNER_HUMAN_NAME,
    COL_PLATFORM,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_INSTALLED,
    COL_INSTALLED_AT,
    COL_INSTALLED_AT_TEXT,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT
)


class GameStore(GObject.Object):
    __gsignals__ = {
        "media-loaded": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "icon-loaded": (GObject.SIGNAL_RUN_FIRST, None, (str, str)),
        "icons-changed": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "sorting-changed": (GObject.SIGNAL_RUN_FIRST, None, (str, bool)),
    }

    sort_columns = {
        "name": COL_NAME,
        "year": COL_YEAR,
        "runner": COL_RUNNER_HUMAN_NAME,
        "platform": COL_PLATFORM,
        "lastplayed": COL_LASTPLAYED,
        "installed_at": COL_INSTALLED_AT,
        "playtime": COL_PLAYTIME
    }

    def __init__(
            self,
            icon_type,
            filter_installed,
            sort_key,
            sort_ascending,
            show_installed_first=False,
    ):
        super(GameStore, self).__init__()
        self.games = pga.get_games(show_installed_first=show_installed_first)
        self.games_to_refresh = set()
        self.icon_type = icon_type
        self.filter_installed = filter_installed
        self.show_installed_first = show_installed_first
        self.filter_text = None
        self.filter_runner = None
        self.filter_platform = None
        self.store = Gtk.ListStore(
            int,
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
            str,
            str,
        )
        if show_installed_first:
            self.store.set_sort_column_id(COL_INSTALLED, Gtk.SortType.DESCENDING)
        else:
            self.store.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)
        self.prevent_sort_update = False  # prevent recursion with signals
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(self.filter_view)
        self.modelsort = Gtk.TreeModelSort.sort_new_with_model(self.modelfilter)
        self.modelsort.connect("sort-column-changed", self.on_sort_column_changed)
        self.sort_view(sort_key, sort_ascending)
        self.medias = {
            "banner": {},
            "icon": {}
        }
        self.media_loaded = False
        self.connect('media-loaded', self.on_media_loaded)
        self.connect('icon-loaded', self.on_icon_loaded)
        AsyncCall(self.get_missing_media)

    def __str__(self):
        return (
            "GameStore: <filter_installed: {filter_installed}, "
            "filter_text: {filter_text}>".format(**self.__dict__)
        )

    def load(self):
        self.add_games(self.games)

    @property
    def game_slugs(self):
        return [game["slug"] for game in self.games]

    def add_games(self, games):
        """Add games to the store"""
        for game in list(games):
            GLib.idle_add(self.add_game, game)

    def add_games_by_ids(self, game_ids):
        self.media_loaded = False
        games = pga.get_games_by_ids(game_ids)
        game_slugs = [game["slug"] for game in games]
        GLib.idle_add(self.get_missing_media, game_slugs)
        self.add_games(games)

    def has_icon(self, game_slug, media_type=None):
        """Return True if the game_slug has the icon of `icon_type`"""
        media_type = media_type or self.icon_type
        return system.path_exists(get_icon_path(game_slug, media_type))

    def get_missing_media(self, slugs=None):
        """Query the Lutris.net API for missing icons"""
        slugs = slugs or self.game_slugs
        unavailable_banners = [
            slug for slug in slugs if not self.has_icon(slug, "banner")
        ]
        unavailable_icons = [
            slug for slug in slugs if not self.has_icon(slug, "icon")
        ]

        # Remove duplicate slugs
        missing_media_slugs = list(set(unavailable_banners) | set(unavailable_icons))
        if not missing_media_slugs:
            return
        logger.debug(
            "Requesting missing icons from API for %d games", len(missing_media_slugs)
        )
        lutris_media = api.get_api_games(missing_media_slugs)
        if not lutris_media:
            return

        for game in lutris_media:
            if game["slug"] in unavailable_banners and game["banner_url"]:
                self.medias["banner"][game["slug"]] = game["banner_url"]
            if game["slug"] in unavailable_icons and game["icon_url"]:
                self.medias["icon"][game["slug"]] = game["icon_url"]
        self.media_loaded = True
        self.emit("media-loaded")

    def filter_view(self, model, _iter, filter_data=None):
        """Filter function for the game model"""
        if self.filter_installed:
            installed = model.get_value(_iter, COL_INSTALLED)
            if not installed:
                return False
        if self.filter_text:
            name = model.get_value(_iter, COL_NAME)
            if not self.filter_text.lower() in name.lower():
                return False
        if self.filter_runner:
            runner = model.get_value(_iter, COL_RUNNER)
            if not self.filter_runner == runner:
                return False
        if self.filter_platform:
            platform = model.get_value(_iter, COL_PLATFORM)
            if platform != self.filter_platform:
                return False
        return True

    def sort_view(self, key="name", ascending=True):
        self.modelsort.set_sort_column_id(
            self.sort_columns[key],
            Gtk.SortType.ASCENDING if ascending else Gtk.SortType.DESCENDING,
        )

    def on_sort_column_changed(self, model):
        if self.prevent_sort_update:
            return
        (col, direction) = model.get_sort_column_id()
        key = next((c for c, k in self.sort_columns.items() if k == col), None)
        ascending = direction == Gtk.SortType.ASCENDING
        self.prevent_sort_update = True
        self.sort_view(key, ascending)
        self.prevent_sort_update = False
        self.emit("sorting-changed", key, ascending)

    def get_row_by_id(self, game_id):
        for model_row in self.store:
            if model_row[COL_ID] == int(game_id):
                return model_row

    def remove_game(self, game_id):
        """Remove a game from the view."""
        game_index = 0
        for index, game in enumerate(self.games):
            if game["id"] == game_id:
                game_index = index
                break
        if game_index:
            self.games.pop(game_index)
        else:
            logger.warning("Can't find game %s in game list", game_id)
        row = self.get_row_by_id(game_id)
        self.store.remove(row.iter)

    def update_game_by_id(self, game_id):
        """Update game informations."""
        game = pga.get_game_by_field(game_id, "id")
        return self.update(game)

    def update(self, pga_game):
        game = PgaGame(pga_game)
        row = self.get_row_by_id(game.id)
        if not row:
            raise ValueError("No existing row for game %s" % game.slug)
        row[COL_ID] = game.id
        row[COL_SLUG] = game.slug
        row[COL_NAME] = game.name
        row[COL_ICON] = game.get_pixbuf(self.icon_type)
        row[COL_YEAR] = game.year
        row[COL_RUNNER] = game.runner
        row[COL_RUNNER_HUMAN_NAME] = game.runner_text
        row[COL_PLATFORM] = game.platform
        row[COL_LASTPLAYED] = game.lastplayed
        row[COL_LASTPLAYED_TEXT] = game.lastplayed_text
        row[COL_INSTALLED] = game.installed
        row[COL_INSTALLED_AT] = game.installed_at
        row[COL_INSTALLED_AT_TEXT] = game.installed_at_text
        row[COL_PLAYTIME] = game.playtime
        row[COL_PLAYTIME_TEXT] = game.playtime_text
        if not self.has_icon(game.slug):
            self.refresh_icon(game.slug)

    def refresh_icon(self, game_slug):
        AsyncCall(self.fetch_icon, None, game_slug)

    def on_icon_loaded(self, _store, game_slug, media_type):
        if not self.has_icon(game_slug):
            return
        if media_type != self.icon_type:
            return
        for pga_game in pga.get_games_where(slug=game_slug):
            GLib.idle_add(self.update, pga_game)

    def fetch_icon(self, slug):
        if not self.media_loaded:
            self.games_to_refresh.add(slug)
            return

        for media_type in ('banner', 'icon'):
            url = self.medias[media_type].get(slug)
            if url:
                download_media(url, get_icon_path(slug, media_type))
                self.emit('icon-loaded', slug, media_type)

    def on_media_loaded(self, response):
        for slug in self.games_to_refresh:
            self.refresh_icon(slug)

    def add_game_by_id(self, game_id):
        """Add a game into the store."""
        game = pga.get_game_by_field(game_id, "id")
        return self.add_game(game)

    def add_game(self, pga_game):
        game = PgaGame(pga_game)
        self.games.append(pga_game)
        self.store.append(
            (
                game.id,
                game.slug,
                game.name,
                game.get_pixbuf(self.icon_type),
                game.year,
                game.runner,
                game.runner_text,
                game.platform,
                game.lastplayed,
                game.lastplayed_text,
                game.installed,
                game.installed_at,
                game.installed_at_text,
                game.playtime,
                game.playtime_text
            )
        )
        if not self.has_icon(game.slug):
            self.refresh_icon(game.slug)

    def add_or_update(self, game_id):
        try:
            self.update_game_by_id(game_id)
        except ValueError:
            self.add_game_by_id(game_id)

    def set_icon_type(self, icon_type):
        if icon_type != self.icon_type:
            self.icon_type = icon_type
            for row in self.store:
                row[COL_ICON] = get_pixbuf_for_game(
                    row[COL_SLUG], icon_type, is_installed=row[COL_INSTALLED]
                )
            self.emit("icons-changed", icon_type)
