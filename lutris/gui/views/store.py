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
    COL_LASTPLAYED_TEXT,
    COL_INSTALLED,
    COL_INSTALLED_AT_TEXT,
    COL_PLAYTIME_TEXT,
)

sortings = {
    "name": COL_NAME,
    "year": COL_YEAR,
    "runner": COL_RUNNER_HUMAN_NAME,
    "platform": COL_PLATFORM,
    "lastplayed": COL_LASTPLAYED_TEXT,
    "installed_at": COL_INSTALLED_AT_TEXT,
    "playtime": COL_PLAYTIME_TEXT
}


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
        self.games = games
        self.icon_type = icon_type
        self.filter_installed = filter_installed
        self.show_installed_first = show_installed_first
        self.filter_text = None
        self.filter_runner = None
        self.filter_platform = None
        self.runner_names = self.populate_runner_names()
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
        if games:
            self.fill_store(games)

    def __str__(self):
        return (
            "GameStore: <filter_installed: {filter_installed}, "
            "filter_text: {filter_text}>".format(**self.__dict__)
        )

    def get_ids(self):
        return [row[COL_ID] for row in self.store]

    def populate_runner_names(self):
        names = {}
        for runner in runners.__all__:
            runner_inst = runners.import_runner(runner)
            names[runner] = runner_inst.human_name
        return names

    def fill_store(self, games):
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

    def get_runner_info(self, game):
        if not game["runner"]:
            return
        runner_human_name = self.runner_names.get(game["runner"], "")
        platform = game["platform"]
        if not platform and game["installed"]:
            game_inst = Game(game["id"])
            platform = game_inst.platform
            if not platform:
                game_inst.set_platform_from_runner()
                platform = game_inst.platform
                logger.debug("Setting platform for %s: %s", game["name"], platform)

        return runner_human_name, platform

    def add_game(self, game):
        platform = ""
        runner_human_name = ""
        runner_info = self.get_runner_info(game)
        if runner_info:
            runner_human_name, platform = runner_info
        else:
            game["installed"] = False

        lastplayed_text = ""
        if game["lastplayed"]:
            lastplayed_text = time.strftime("%c", time.localtime(game["lastplayed"]))

        installed_at_text = ""
        if game["installed_at"]:
            installed_at_text = time.strftime(
                "%c", time.localtime(game["installed_at"])
            )

        pixbuf = get_pixbuf_for_game(game["slug"], self.icon_type, game["installed"])
        try:
            playtime_text = get_formatted_playtime(game["playtime"])
        except ValueError:
            # We're all screwed
            pga.unfuck_playtime(game)
            playtime_text = game["playtime"] + ":("

        self.store.append(
            (
                game["id"],
                gtk_safe(game["slug"]),
                gtk_safe(game["name"]),
                pixbuf,
                gtk_safe(str(game["year"] or "")),
                gtk_safe(game["runner"]),
                gtk_safe(runner_human_name),
                gtk_safe(platform),
                game["lastplayed"],
                gtk_safe(lastplayed_text),
                game["installed"],
                game["installed_at"],
                gtk_safe(installed_at_text),
                game["playtime"],
                playtime_text,
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
