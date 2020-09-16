"""Store object for a list of games"""
# pylint: disable=not-an-iterable
import concurrent.futures

from gi.repository import GLib, GObject, Gtk
from gi.repository.GdkPixbuf import Pixbuf

from lutris import api
from lutris.database.games import get_games_by_slug
from lutris.gui.views.store_item import StoreItem
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
# from lutris.util.http import download_file
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


class MediaLoader(GObject.Object):
    __gsignals__ = {
        "api-loaded": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "icon-loaded": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
    }

    def __init__(self, service_media):
        super().__init__()
        self.service_media = service_media

        self.games_to_refresh = set()
        self.medias = {}
        self.misses = set()
        self.api_loaded = False
        self.connect("api-loaded", self.on_api_loaded)

    def refresh_icon(self, game_slug, force=False):
        if not self.service_media.exists(game_slug) or force:
            AsyncCall(self.fetch_icon, None, game_slug)

    def fetch_icon(self, slug):
        if not self.api_loaded:
            self.games_to_refresh.add(slug)
            return

        # XXX there is no self.medias
        # for media_type in ("banner", "icon"):
        #     url = self.medias[media_type].get(slug)
        #     if url:
        #         logger.debug("Getting %s for %s: %s", media_type, slug, url)
        #         # FIXME set dest path accordingly
        #         # download_file(url, get_icon_path(slug, media_type))
        #         self.emit("icon-loaded", slug)

    def get_missing_media(self, slugs):
        """Query the Lutris.net API for missing icons"""
        unavailable_media = {slug for slug in slugs if not self.service_media.exists(slug)}

        # Remove duplicate slugs
        missing_media_slugs = (unavailable_media - self.misses)
        if not missing_media_slugs:
            return
        if len(missing_media_slugs) > 10:
            logger.debug("Requesting missing icons from API for %d games", len(missing_media_slugs))
        else:
            logger.debug("Requesting missing icons from API for %s", ", ".join(missing_media_slugs))

        lutris_media = api.get_api_games(list(missing_media_slugs), inject_aliases=True)
        if not lutris_media:
            return

        for game in lutris_media:
            if game["slug"] in unavailable_media and game["icon_url"]:
                self.medias[game["slug"]] = game["icon_url"]
                unavailable_media.remove(game["slug"])
        self.misses = unavailable_media
        self.api_loaded = True
        self.emit("api-loaded")

    def on_api_loaded(self, _response):
        """Callback to handle a response from the API with the new media"""
        self.download_icons(self.medias)

    def download_icons(self, medias):
        """Download a list of media files concurrently.

        Limits the number of simultaneous downloads to avoid API throttling
        and UI being overloaded with signals.
        """
        if not medias:
            return

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_downloads = {
                executor.submit(self.service_media.download, slug): slug
                for slug in medias
            }
            for future in concurrent.futures.as_completed(future_downloads):
                slug = future_downloads[future]
                try:
                    future.result()
                except Exception as ex:  # pylint: disable=broad-except
                    logger.exception('%r failed: %s', slug, ex)
                else:
                    self.emit("icon-loaded", slug)
        # XXX clearly not the place for this
        # if media_type == "icon":
        #     system.update_desktop_icons()


class GameStore(GObject.Object):
    __gsignals__ = {
        "icons-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, service_media):
        super().__init__()
        self.service_media = service_media

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
        self.media_loader = MediaLoader(service_media)
        self.media_loader.connect("icon-loaded", self.on_icon_loaded)

    def add_games(self, games):
        """Add games to the store"""
        self.media_loader.api_loaded = False
        if games:
            AsyncCall(self.media_loader.get_missing_media, None, [game["slug"] for game in games])
        for game in list(games):
            GLib.idle_add(self.add_game, game)

    def get_row_by_id(self, game_id):
        for model_row in self.store:
            if model_row[COL_ID] == int(game_id):
                return model_row

    def remove_game(self, game_id):
        """Remove a game from the view."""
        row = self.get_row_by_id(game_id)
        if row:
            self.store.remove(row.iter)

    def update(self, db_game):
        """Update game informations."""
        game = StoreItem(db_game)
        row = self.get_row_by_id(game.id)
        if not row:
            raise ValueError("No existing row for game %s" % game.slug)
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
        self.media_loader.refresh_icon(game.slug)

    def add_game(self, db_game):
        """Add a PGA game to the store"""
        game = StoreItem(db_game)
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
        self.media_loader.refresh_icon(game.slug)

    def set_service_media(self, service_media):
        """Change the icon type"""
        if service_media == self.service_media:
            return
        self.service_media = service_media
        for row in self.store:
            row[COL_ICON] = get_pixbuf_for_game(
                row[COL_SLUG],
                self.service_media.size,
                is_installed=row[COL_INSTALLED],
            )
        self.emit("icons-changed")

    def on_icon_loaded(self, game_slug):
        """Callback signal for when a icon has downloaded.
        Update the image in the view.
        """
        for pga_game in get_games_by_slug(game_slug):
            logger.debug("Updating %s", pga_game["id"])
            GLib.idle_add(self.update, pga_game)
