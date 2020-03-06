"""Store object for a list of games"""
# pylint: disable=not-an-iterable
import concurrent.futures
from gi.repository import Gtk, GObject, GLib
from gi.repository.GdkPixbuf import Pixbuf
from lutris import pga
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.util.resources import get_icon_path, download_media, update_desktop_icons
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
    COL_PLAYTIME_TEXT,
)


def try_lower(value):
    try:
        out = value.lower()
    except AttributeError:
        out = value
    return out


def sort_func(model, row1, row2, sort_col):
    """Sorting function for the GameStore"""
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
        "playtime": COL_PLAYTIME,
    }

    def __init__(
            self,
            games,
            icon_type,
            filter_installed,
            sort_key,
            sort_ascending,
            show_hidden_games,
            show_installed_first=False,
    ):
        super(GameStore, self).__init__()
        self.games = games or pga.get_games(show_installed_first=show_installed_first)
        if not show_hidden_games:
            # Check if the PGA contains game IDs that the user does not
            # want to see
            self.games = [
                game for game in self.games if game["id"] not in pga.get_hidden_ids()
            ]

        self.search_mode = False
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
        sort_col = COL_NAME
        if show_installed_first:
            sort_col = COL_INSTALLED
            self.store.set_sort_column_id(sort_col, Gtk.SortType.DESCENDING)
        else:
            self.store.set_sort_column_id(sort_col, Gtk.SortType.ASCENDING)
        self.prevent_sort_update = False  # prevent recursion with signals
        self.modelfilter = self.store.filter_new()
        self.modelfilter.set_visible_func(self.filter_view)
        try:
            self.modelsort = Gtk.TreeModelSort.sort_new_with_model(self.modelfilter)
        except AttributeError:
            # Apparently some API breaking changes on GTK minor versions.
            self.modelsort = Gtk.TreeModelSort.new_with_model(self.modelfilter)
        self.modelsort.connect("sort-column-changed", self.on_sort_column_changed)
        self.modelsort.set_sort_func(sort_col, sort_func, sort_col)
        self.sort_view(sort_key, sort_ascending)
        self.medias = {"banner": {}, "icon": {}}
        self.banner_misses = set()
        self.icon_misses = set()
        self.media_loaded = False
        self.connect("media-loaded", self.on_media_loaded)
        self.connect("icon-loaded", self.on_icon_loaded)

    def __str__(self):
        return (
            "GameStore: <filter_installed: {filter_installed}, "
            "filter_text: {filter_text}>".format(**self.__dict__)
        )

    def load(self, from_search=False):
        if not self.games:
            return
        self.search_mode = from_search
        self.add_games(self.games)

    @property
    def game_slugs(self):
        return [game["slug"] for game in self.games]

    def add_games(self, games):
        """Add games to the store"""
        self.media_loaded = False
        if games:
            AsyncCall(self.get_missing_media, None, [game["slug"] for game in games])
        for game in list(games):
            GLib.idle_add(self.add_game, game)

    def has_icon(self, game_slug, media_type=None):
        """Return True if the game_slug has the icon of `icon_type`"""
        media_type = media_type or self.icon_type
        return system.path_exists(get_icon_path(game_slug, media_type))

    def get_missing_media(self, slugs=None):
        """Query the Lutris.net API for missing icons"""
        slugs = slugs or self.game_slugs
        unavailable_banners = {
            slug for slug in slugs
            if not self.has_icon(slug, "banner")
        }
        unavailable_icons = {
            slug for slug in slugs
            if not self.has_icon(slug, "icon")
        }

        # Remove duplicate slugs
        missing_media_slugs = (
            (unavailable_banners - self.banner_misses)
            | (unavailable_icons - self.icon_misses)
        )
        if not missing_media_slugs:
            return
        if len(missing_media_slugs) > 10:
            logger.debug(
                "Requesting missing icons from API for %d games", len(missing_media_slugs)
            )
        else:
            logger.debug(
                "Requesting missing icons from API for %s", ", ".join(missing_media_slugs)
            )

        lutris_media = api.get_api_games(list(missing_media_slugs), inject_aliases=True)
        if not lutris_media:
            return

        for game in lutris_media:
            if game["slug"] in unavailable_banners and game["banner_url"]:
                self.medias["banner"][game["slug"]] = game["banner_url"]
                unavailable_banners.remove(game["slug"])
            if game["slug"] in unavailable_icons and game["icon_url"]:
                self.medias["icon"][game["slug"]] = game["icon_url"]
                unavailable_icons.remove(game["slug"])
        self.banner_misses = unavailable_banners
        self.icon_misses = unavailable_icons
        self.media_loaded = True
        self.emit("media-loaded")

    def filter_view(self, model, _iter, _filter_data=None):
        """Filter function for the game model"""
        if self.search_mode:
            return True
        if self.filter_installed:
            installed = model.get_value(_iter, COL_INSTALLED)
            if not installed and not self.search_mode:
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
        """Sort the model on a given column name"""
        try:
            sort_column = self.sort_columns[key]
        except KeyError:
            logger.error("Invalid column name '%s'", key)
            sort_column = COL_NAME
        self.modelsort.set_sort_column_id(
            sort_column,
            Gtk.SortType.ASCENDING if ascending else Gtk.SortType.DESCENDING,
        )

    def on_sort_column_changed(self, model):
        if self.prevent_sort_update:
            return
        (col, direction) = model.get_sort_column_id()
        key = next((c for c, k in self.sort_columns.items() if k == col), None)
        ascending = direction == Gtk.SortType.ASCENDING
        self.prevent_sort_update = True
        if not key:
            raise ValueError("Invalid sort key for col %s" % col)
        self.sort_view(key, ascending)
        self.prevent_sort_update = False
        self.emit("sorting-changed", key, ascending)

    def get_row_by_id(self, game_id, filtered=False):
        if filtered:
            store = self.modelsort
        else:
            store = self.store
        for model_row in store:
            if model_row[COL_ID] == int(game_id):
                return model_row

    def get_row_by_slug(self, slug):
        """Return a row by its slug.
        Requires slugs to be unique, thus only works for search mode
        """
        if not self.search_mode:
            raise RuntimeError("get_row_by_slug can only be used with search_mode")
        for model_row in self.store:
            if model_row[COL_SLUG] == slug:
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
        if row:
            self.store.remove(row.iter)

    def update_game_by_id(self, game_id):
        pga_game = pga.get_game_by_field(game_id, "id")
        if pga_game:
            return self.update(pga_game)
        return self.remove_game(game_id)

    def update(self, pga_game):
        """Update game informations."""
        game = PgaGame(pga_game)
        if self.search_mode:
            row = self.get_row_by_slug(game.slug)
        else:
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
            logger.debug("%s has no %s", game_slug, media_type)
            return
        if media_type != self.icon_type:
            return
        if self.search_mode:
            GLib.idle_add(self.update_icon, game_slug)
            return
        for pga_game in pga.get_games_by_slug(game_slug):
            logger.debug("Updating %s", pga_game["id"])
            GLib.idle_add(self.update, pga_game)

    def update_icon(self, game_slug):
        row = self.get_row_by_slug(game_slug)
        row[COL_ICON] = get_pixbuf_for_game(game_slug, self.icon_type, True)

    def fetch_icon(self, slug):
        if not self.media_loaded:
            self.games_to_refresh.add(slug)
            return

        for media_type in ("banner", "icon"):
            url = self.medias[media_type].get(slug)
            if url:
                logger.debug("Getting %s for %s: %s", media_type, slug, url)
                download_media(url, get_icon_path(slug, media_type))
                self.emit("icon-loaded", slug, media_type)

    def on_media_loaded(self, _response):
        """Callback to handle a response from the API with the new media"""
        if not self.medias:
            return
        for media_type in ("banner", "icon"):
            self.download_icons([
                (slug, self.medias[media_type][slug], get_icon_path(slug, media_type))
                for slug in self.medias[media_type]
            ], media_type)

    def download_icons(self, downloads, media_type):
        """Download a list of media files concurrently.

        Limits the number of simultaneous downloads to avoid API throttling
        and UI being overloaded with signals.
        """
        if not downloads:
            return

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_downloads = {
                executor.submit(download_media, url, dest_path): slug
                for slug, url, dest_path in downloads
            }
            for future in concurrent.futures.as_completed(future_downloads):
                slug = future_downloads[future]
                try:
                    future.result()
                except Exception as ex:  # pylint: disable=broad-except
                    logger.exception('%r failed: %s', slug, ex)
                else:
                    self.emit("icon-loaded", slug, media_type)
        if media_type == "icon":
            update_desktop_icons()

    def add_games_by_ids(self, game_ids):
        self.add_games(pga.get_games_by_ids(game_ids))

    def add_game_by_id(self, game_id):
        """Add a game into the store."""
        return self.add_games_by_ids([game_id])

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
                game.playtime_text,
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
                    row[COL_SLUG],
                    icon_type,
                    is_installed=row[COL_INSTALLED] if not self.search_mode else True,
                )
            self.emit("icons-changed", icon_type)
