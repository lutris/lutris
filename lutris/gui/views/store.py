"""Store object for a list of games"""
import time
from gi.repository import Gtk, GObject
from gi.repository.GdkPixbuf import Pixbuf
from lutris import runners
from lutris import pga
from lutris.game import Game
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, get_formatted_playtime
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
    COL_INSTALLED,
    COL_INSTALLED_AT,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT
)

sortings = {
    "name": COL_NAME,
    "year": COL_YEAR,
    "runner": COL_RUNNER_HUMAN_NAME,
    "platform": COL_PLATFORM,
    "lastplayed": COL_LASTPLAYED,
    "installed_at": COL_INSTALLED_AT,
    "playtime": COL_PLAYTIME
}


class PgaGame:
    """Representation of a database stored game"""
    def __init__(self, pga_data):
        self._pga_data = pga_data
        runner_names = {}
        for runner in runners.__all__:
            runner_inst = runners.import_runner(runner)
            runner_names[runner] = runner_inst.human_name
        self.runner_names = runner_names

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<PgaGame id=%s slug=%s>" % (self.id, self.slug)

    @property
    def id(self):  # pylint: disable=invalid-name
        """Game internal ID"""
        return self._pga_data["id"]

    @property
    def slug(self):
        """Slug identifier"""
        return gtk_safe(self._pga_data["slug"])

    @property
    def name(self):
        """Name"""
        return gtk_safe(self._pga_data["name"])

    @property
    def year(self):
        """Year"""
        return str(self._pga_data["year"] or "")

    @property
    def runner(self):
        """Runner slug"""
        return gtk_safe(self._pga_data["runner"])

    @property
    def runner_text(self):
        """Runner name"""
        return gtk_safe(self.runner_names.get(self.runner))

    @property
    def platform(self):
        """Platform"""
        _platform = self._pga_data["platform"]
        if not _platform and self.installed:
            game_inst = Game(self._pga_data["id"])
            _platform = game_inst.platform
            if not _platform:
                game_inst.set_platform_from_runner()
                _platform = game_inst.platform
                logger.debug("Setting platform for %s: %s", self, _platform)
        return _platform

    @property
    def installed(self):
        """Game is installed"""
        if not self._pga_data["runner"]:
            return False
        return self._pga_data["installed"]

    def get_pixbuf(self, icon_type):
        """Pixbuf varying on icon type"""
        return get_pixbuf_for_game(
            self._pga_data["slug"],
            icon_type,
            self._pga_data["installed"]
        )

    @property
    def installed_at(self):
        """Date of install"""
        return self._pga_data["installed_at"]

    @property
    def installed_at_text(self):
        """Date of install (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self._pga_data["installed_at"]))
            if self._pga_data["installed_at"] else ""
        )

    @property
    def lastplayed(self):
        """Date of last play"""
        return self._pga_data["lastplayed"]

    @property
    def lastplayed_text(self):
        """Date of last play (textual representation)"""
        return gtk_safe(
            time.strftime("%X %x", time.localtime(self._pga_data["lastplayed"]))
            if self._pga_data["lastplayed"] else ""
        )

    @property
    def playtime(self):
        """Playtime duration in hours"""
        return self._pga_data["playtime"]

    @property
    def playtime_text(self):
        """Playtime duration in hours (textual representation)"""
        try:
            playtime_text = get_formatted_playtime(self._pga_data["playtime"])
        except ValueError:
            # We're all screwed
            logger.warning("Invalid playtime value %s for %s", self.playtime, self)
            pga.fix_playtime(self._pga_data)
            playtime_text = ""  # Do not show erroneous values
        return playtime_text


class GameStore(GObject.Object):
    __gsignals__ = {
        "icons-changed": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "sorting-changed": (GObject.SIGNAL_RUN_FIRST, None, (str, bool)),
    }

    def __init__(
            self,
            games,
            icon_type,
            filter_installed,
            sort_key,
            sort_ascending,
            show_installed_first=False,
    ):
        super(GameStore, self).__init__()
        self.games = games or []
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
        self.sort_view(sort_key, sort_ascending)
        self.modelsort.connect("sort-column-changed", self.on_sort_column_changed)
        self.add_games(games)

    def __str__(self):
        return (
            "GameStore: <filter_installed: {filter_installed}, "
            "filter_text: {filter_text}>".format(**self.__dict__)
        )

    def get_ids(self):
        return [row[COL_ID] for row in self.store]

    def add_games(self, games):
        """Add games to the store"""
        for game in games:
            self.add_game(game)

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
            sortings[key],
            Gtk.SortType.ASCENDING if ascending else Gtk.SortType.DESCENDING,
        )

    def on_sort_column_changed(self, model):
        if self.prevent_sort_update:
            return
        (col, direction) = model.get_sort_column_id()
        key = next((c for c, k in sortings.items() if k == col), None)
        ascending = direction == Gtk.SortType.ASCENDING
        self.prevent_sort_update = True
        self.sort_view(key, ascending)
        self.prevent_sort_update = False
        self.emit("sorting-changed", key, ascending)

    def add_game_by_id(self, game_id):
        """Add a game into the store."""
        if not game_id:
            return
        game = pga.get_game_by_field(game_id, "id")
        if not game or "slug" not in game:
            raise ValueError("Can't find game {} ({})".format(game_id, game))
        self.add_game(game)

    def get_row_by_id(self, game_id):
        for model_row in self.store:
            if model_row[COL_ID] == int(game_id):
                return model_row

    def has_game_id(self, game_id):
        return bool(self.get_row_by_id(game_id))

    def remove_game(self, removed_id):
        """Remove a game from the view."""
        row = self.get_row_by_id(removed_id)
        self.store.remove(row.iter)

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
        row[COL_YEAR] = str(game_year)
        row[COL_PLAYTIME] = game_playtime
        row[COL_PLAYTIME_TEXT] = get_formatted_playtime(game_playtime)

        self.update_image(game_id, row[COL_INSTALLED])

    def update_image(self, game_id, is_installed=False):
        """Update game icon."""
        row = self.get_row_by_id(game_id)
        game_slug = row[COL_SLUG]
        game_pixbuf = get_pixbuf_for_game(
            game_slug, self.icon_type, is_installed
        )
        row[COL_ICON] = game_pixbuf
        row[COL_INSTALLED] = is_installed
        # if "GameGridView" in self.__class__.__name__:
        #     GLib.idle_add(self.queue_draw)

    def add_game(self, pga_game):
        game = PgaGame(pga_game)
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

    def set_icon_type(self, icon_type):
        if icon_type != self.icon_type:
            self.icon_type = icon_type
            for row in self.store:
                row[COL_ICON] = get_pixbuf_for_game(
                    row[COL_SLUG], icon_type, is_installed=row[COL_INSTALLED]
                )
            self.emit("icons-changed", icon_type)  # Obsolete, only for GridView
