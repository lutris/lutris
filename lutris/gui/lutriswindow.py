"""Main window for the Lutris interface."""

# pylint: disable=too-many-lines
# pylint: disable=no-member
import os
from collections import namedtuple
from gettext import gettext as _
from typing import List
from urllib.parse import unquote, urlparse

from gi.repository import Gdk, Gio, GLib, GObject, Gtk

from lutris import services, settings
from lutris.api import (
    LUTRIS_ACCOUNT_CONNECTED,
    LUTRIS_ACCOUNT_DISCONNECTED,
    get_runtime_versions,
    read_user_info,
)
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.exceptions import EsyncLimitError
from lutris.game import GAME_INSTALLED, GAME_STOPPED, GAME_UNHANDLED_ERROR, GAME_UPDATED, Game
from lutris.gui import dialogs
from lutris.gui.addgameswindow import AddGamesWindow
from lutris.gui.config.preferences_dialog import PreferencesDialog
from lutris.gui.dialogs import ClientLoginDialog, ErrorDialog, QuestionDialog, get_error_handler, register_error_handler
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate, DialogLaunchUIDelegate
from lutris.gui.dialogs.game_import import ImportGameDialog
from lutris.gui.download_queue import DownloadQueue
from lutris.gui.views.grid import GameGridView
from lutris.gui.views.list import GameListView
from lutris.gui.views.store import GameStore
from lutris.gui.widgets.game_bar import GameBar
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.sidebar import LutrisSidebar
from lutris.gui.widgets.utils import load_icon_theme, open_uri
from lutris.runtime import ComponentUpdater, RuntimeUpdater
from lutris.search import GameSearch
from lutris.services.base import SERVICE_GAMES_LOADED, SERVICE_LOGIN, SERVICE_LOGOUT
from lutris.services.lutris import LutrisService
from lutris.util import datapath
from lutris.util.jobs import COMPLETED_IDLE_TASK, AsyncCall, schedule_at_idle
from lutris.util.library_sync import LOCAL_LIBRARY_UPDATED, LibrarySyncer
from lutris.util.log import logger
from lutris.util.path_cache import MISSING_GAMES, add_to_path_cache
from lutris.util.strings import get_natural_sort_key
from lutris.util.system import update_desktop_icons


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "lutris-window.ui"))
class LutrisWindow(Gtk.ApplicationWindow, DialogLaunchUIDelegate, DialogInstallUIDelegate):  # pylint: disable=too-many-public-methods
    """Handler class for main window signals."""

    default_view_type = "grid"
    default_width = 800
    default_height = 600

    __gtype_name__ = "LutrisWindow"
    games_stack: Gtk.Stack = GtkTemplate.Child()
    sidebar_revealer: Gtk.Revealer = GtkTemplate.Child()
    sidebar_scrolled: Gtk.ScrolledWindow = GtkTemplate.Child()
    game_revealer: Gtk.Revealer = GtkTemplate.Child()
    search_entry: Gtk.SearchEntry = GtkTemplate.Child()
    zoom_adjustment: Gtk.Adjustment = GtkTemplate.Child()
    blank_overlay: Gtk.Alignment = GtkTemplate.Child()
    viewtype_icon: Gtk.Image = GtkTemplate.Child()
    download_revealer: Gtk.Revealer = GtkTemplate.Child()
    game_view_spinner: Gtk.Spinner = GtkTemplate.Child()
    login_notification_revealer: Gtk.Revealer = GtkTemplate.Child()
    lutris_log_in_label: Gtk.Label = GtkTemplate.Child()
    turn_on_library_sync_label: Gtk.Label = GtkTemplate.Child()
    version_notification_revealer: Gtk.Revealer = GtkTemplate.Child()
    version_notification_label: Gtk.Revealer = GtkTemplate.Child()

    def __init__(self, application, **kwargs) -> None:
        width = int(settings.read_setting("width") or self.default_width)
        height = int(settings.read_setting("height") or self.default_height)
        super().__init__(
            default_width=width,
            default_height=height,
            window_position=Gtk.WindowPosition.NONE,
            name="lutris",
            icon_name="lutris",
            application=application,
            **kwargs,
        )
        update_desktop_icons()
        load_icon_theme()
        self.application = application
        self.window_x, self.window_y = self.get_position()
        self.restore_window_position()
        self.threads_stoppers = []
        self.window_size = (width, height)
        self.maximized = settings.read_setting("maximized") == "True"
        self.service = None
        self.search_timer_task = COMPLETED_IDLE_TASK
        self.filters = self.load_filters()
        self.game_search = None
        self.set_service(self.filters.get("service"))
        self.icon_type = self.load_icon_type()
        self.game_store = GameStore(self.service, self.service_media)
        self._game_store_generation = 0
        self.current_view = Gtk.Box()
        self.views = {}

        self.dynamic_categories_game_factories = {
            "recent": self.get_recent_games,
            "missing": self.get_missing_games,
            "running": self.get_running_games,
        }

        self.connect("delete-event", self.on_window_delete)
        self.connect("configure-event", self.on_window_configure)
        self.connect("realize", self.on_load)
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("notify::visible", self.on_visible_changed)
        if self.maximized:
            self.maximize()
        self.init_template()
        self._init_actions()

        # Setup Drag and drop
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_add_uri_targets()

        self.set_viewtype_icon(self.current_view_type)

        lutris_icon = Gtk.Image.new_from_icon_name("lutris", Gtk.IconSize.MENU)
        lutris_icon.set_margin_right(3)

        self.sidebar = LutrisSidebar(self.application)
        self.sidebar.connect("selected-rows-changed", self.on_sidebar_changed)
        # "realize" is order sensitive- must connect after sidebar itself connects the same signal
        self.sidebar.connect("realize", self.on_sidebar_realize)
        self.sidebar_scrolled.add(self.sidebar)

        # This must wait until the selected-rows-changed signal is connected
        self.sidebar.initialize_rows()

        self.sidebar_revealer.set_reveal_child(self.side_panel_visible)
        self.sidebar_revealer.set_transition_duration(300)

        self.game_bar = None
        self.revealer_box = Gtk.HBox(visible=True)
        self.game_revealer.add(self.revealer_box)

        self.update_action_state()
        self.update_notification()

        SERVICE_LOGIN.register(self.on_service_login)
        SERVICE_LOGOUT.register(self.on_service_logout)
        SERVICE_GAMES_LOADED.register(self.on_service_games_loaded)
        GAME_UPDATED.register(self.on_game_updated)
        GAME_STOPPED.register(self.on_game_stopped)
        GAME_INSTALLED.register(self.on_game_installed)
        GAME_UNHANDLED_ERROR.register(self.on_game_unhandled_error)
        GObject.add_emission_hook(PreferencesDialog, "settings-changed", self.on_settings_changed)
        MISSING_GAMES.updated.register(self.update_missing_games_sidebar_row)
        LUTRIS_ACCOUNT_CONNECTED.register(self.on_lutris_account_connected)
        LUTRIS_ACCOUNT_DISCONNECTED.register(self.on_lutris_account_disconnected)
        LOCAL_LIBRARY_UPDATED.register(self.on_local_library_updated)

        # Finally trigger the initialization of the view here
        selected_category = settings.read_setting("selected_category", default="runner:all")
        self.sidebar.selected_category = selected_category.split(":", maxsplit=1) if selected_category else None

        schedule_at_idle(self.sync_library, delay_seconds=1.0)

    def _init_actions(self):
        Action = namedtuple("Action", ("callback", "type", "enabled", "default", "accel"))
        Action.__new__.__defaults__ = (None, None, None, None, None)

        actions = {
            "add-game": Action(self.on_add_game_button_clicked),
            "preferences": Action(self.on_preferences_activate),
            "about": Action(self.on_about_clicked),
            "show-installed-only": Action(  # delete?
                self.on_show_installed_state_change,
                type="b",
                default=self.filter_installed,
                accel="<Primary>i",
            ),
            "toggle-viewtype": Action(self.on_toggle_viewtype),
            "toggle-badges": Action(
                self.on_toggle_badges,
                type="b",
                default=settings.read_setting("hide_badges_on_icons"),
                accel="<Primary>p",
            ),
            "icon-type": Action(self.on_icontype_state_change, type="s", default=self.icon_type),
            "view-sorting": Action(
                self.on_view_sorting_state_change,
                type="s",
                default=self.view_sorting,
                enabled=lambda: self.is_view_sort_sensitive,
            ),
            "view-sorting-installed-first": Action(
                self.on_view_sorting_installed_first_change,
                type="b",
                default=self.view_sorting_installed_first,
                enabled=lambda: self.is_view_sort_sensitive,
            ),
            "view-reverse-order": Action(
                self.on_view_sorting_direction_change,
                type="b",
                default=self.view_reverse_order,
                enabled=lambda: self.is_view_sort_sensitive,
            ),
            "show-side-panel": Action(
                self.on_side_panel_state_change,
                type="b",
                default=self.side_panel_visible,
                accel="F9",
            ),
            "show-hidden-games": Action(
                self.on_show_hidden_clicked,
                enabled=lambda: self.is_show_hidden_sensitive,
                accel="<Primary>h",
            ),
            "open-forums": Action(lambda *x: open_uri("https://forums.lutris.net/")),
            "open-discord": Action(lambda *x: open_uri("https://discord.gg/Pnt5CuY")),
            "donate": Action(lambda *x: open_uri("https://lutris.net/donate")),
        }

        self.actions = {}
        self.action_state_updaters = []
        app = self.props.application
        for name, value in actions.items():
            if not value.type:
                action = Gio.SimpleAction.new(name)
                action.connect("activate", value.callback)
            else:
                default_value = None
                param_type = None
                if value.default is not None:
                    default_value = GLib.Variant(value.type, value.default)
                if value.type != "b":
                    param_type = default_value.get_type()
                action = Gio.SimpleAction.new_stateful(name, param_type, default_value)
                action.connect("change-state", value.callback)
            self.actions[name] = action
            if value.enabled:

                def updater(action=action, value=value):
                    action.props.enabled = value.enabled()

                self.action_state_updaters.append(updater)
            self.add_action(action)
            if value.accel:
                app.add_accelerator(value.accel, "win." + name)

    def sync_library(self, force: bool = False) -> None:
        """Tasks that can be run after the UI has been initialized."""
        if settings.read_bool_setting("library_sync_enabled"):
            AsyncCall(LibrarySyncer().sync_local_library, None, force=force)

    def update_action_state(self):
        """This invokes the functions to update the enabled states of all the actions
        which can be disabled."""
        for updater in self.action_state_updaters:
            updater()

    @property
    def service_media(self):
        return self.get_service_media(self.load_icon_type())

    @property
    def selected_category(self):
        return self.sidebar.selected_category

    def on_load(self, widget, data=None):
        """Finish initializing the view"""
        self._bind_zoom_adjustment()
        self.current_view.grab_focus()

    def on_sidebar_realize(self, widget, data=None):
        """Grab the initial focus after the sidebar is initialized - so the view is ready."""
        self.current_view.grab_focus()

    def on_drag_data_received(self, _widget, _drag_context, _x, _y, data, _info, _time):
        """Handler for drop event"""
        file_paths = [unquote(urlparse(uri).path) for uri in data.get_uris()]
        dialog = ImportGameDialog(file_paths, parent=self)
        dialog.show()

    def load_filters(self):
        """Load the initial filters when creating the view"""
        # The main sidebar-category filter will be populated when the sidebar row is selected, after this
        return {"installed": self.filter_installed}

    @property
    def is_show_hidden_sensitive(self):
        """True if there are any hiden games to show."""
        return bool(categories_db.get_game_ids_for_categories([".hidden"]))

    def on_show_hidden_clicked(self, action, value):
        """Hides or shows the hidden games"""
        self.sidebar.hidden_row.show()
        self.sidebar.selected_category = "category", ".hidden"

    @property
    def current_view_type(self):
        """Returns which kind of view is currently presented (grid or list)"""
        return settings.read_setting("view_type") or "grid"

    @property
    def filter_installed(self):
        return settings.read_bool_setting("filter_installed", False)

    @property
    def side_panel_visible(self):
        return settings.read_bool_setting("side_panel_visible", True)

    @property
    def show_tray_icon(self):
        """Setting to hide or show status icon"""
        return settings.read_bool_setting("show_tray_icon", False)

    @property
    def view_sorting(self):
        value = settings.read_setting("view_sorting") or "name"
        if value.endswith("_text"):
            value = value[:-5]
        return value

    @property
    def view_reverse_order(self):
        return settings.read_bool_setting("view_reverse_order", False)

    @property
    def view_sorting_installed_first(self):
        return settings.read_bool_setting("view_sorting_installed_first", True)

    @property
    def show_hidden_games(self):
        return settings.read_bool_setting("show_hidden_games", False)

    @property
    def is_view_sort_sensitive(self):
        """True if the view sorting options will be effective; dynamic categories ignore them."""
        return self.filters.get("dynamic_category") not in self.dynamic_categories_game_factories

    def apply_view_sort(self, items, resolver=lambda i: i):
        """This sorts a list of items according to the view settings of this window;
        the items can be anything, but you can provide a lambda that provides a
        database game dictionary for each one; this dictionary carries the
        data we sort on (though any field may be missing).

        This sort always sorts installed games ahead of uninstalled ones, even when
        the sort is set to descending.

        This treats 'name' sorting specially, applying a natural sort so that
        'Mega slap battler 20' comes after 'Mega slap battler 3'."""
        sort_defaults = {
            "name": "",
            "year": 0,
            "lastplayed": 0.0,
            "installed_at": 0.0,
            "playtime": 0.0,
        }

        def get_sort_value(item):
            db_game = resolver(item)
            if not db_game:
                installation_flag = False
                value = sort_defaults.get(self.view_sorting, "")
            else:
                installation_flag = bool(db_game.get("installed"))

                # When sorting by name, check for a valid sortname first, then fall back
                # on name if valid sortname is not available.
                sortname = db_game.get("sortname")
                if self.view_sorting == "name" and sortname:
                    value = sortname
                else:
                    value = db_game.get(self.view_sorting)

                if self.view_sorting == "name":
                    value = get_natural_sort_key(value)
            # Users may have obsolete view_sorting settings, so
            # we must tolerate them. We treat them all as blank.
            value = value or sort_defaults.get(self.view_sorting, "")
            if self.view_sorting == "year":
                contains_year = bool(value)
                if self.view_reverse_order:
                    contains_year = not contains_year
                value = [contains_year, value]
            if self.view_sorting_installed_first:
                # We want installed games to always be first, even in
                # a descending sort.
                if self.view_reverse_order:
                    installation_flag = not installation_flag
                if self.view_sorting == "name":
                    installation_flag = not installation_flag
                return [installation_flag, value]
            return value

        reverse = self.view_reverse_order if self.view_sorting == "name" else not self.view_reverse_order
        return sorted(items, key=get_sort_value, reverse=reverse)

    def get_running_games(self):
        """Return a list of currently running games"""
        return games_db.get_games_by_ids(self.application.get_running_game_ids())

    def get_missing_games(self):
        games = games_db.get_games_by_ids(MISSING_GAMES.missing_game_ids)
        return self.filter_games(games)

    def update_missing_games_sidebar_row(self) -> None:
        missing_games = self.get_missing_games()
        if missing_games:
            self.sidebar.missing_row.show()
            if self.selected_category == ("dynamic_category", "missing"):
                self.update_store()
        else:
            missing_ids = MISSING_GAMES.missing_game_ids
            if missing_ids:
                logger.warning("Path cache out of date? (%s IDs missing)", len(missing_ids))
            self.sidebar.missing_row.hide()

    def get_recent_games(self):
        """Return a list of currently running games"""
        games = games_db.get_games(filters={"installed": "1"})
        games = self.filter_games(games)
        return sorted(games, key=lambda game: max(game["installed_at"] or 0, game["lastplayed"] or 0), reverse=True)

    def get_game_search(self):
        """Returns a game-search object for the current view settings and search text; this object
        is cached so that we need not re-parse the search if it has not changed."""
        text = self.filters.get("text") or ""
        if self.game_search is None or self.game_search.service != self.service or self.game_search.text != text:
            self.game_search = GameSearch(text, self.service)
        return self.game_search

    def filter_games(self, games, implicit_filters: bool = True):
        """Filters a list of games according to the 'installed' and 'text' filters, if those are
        set. But if not, can just return games unchanged."""
        search = self.get_game_search()

        if implicit_filters:
            if self.filters.get("installed") and not search.has_component("installed"):
                search = search.with_predicate(search.get_installed_predicate(installed=True))

            category = self.filters.get("category") or "all"

            if category != ".hidden" and not search.has_component("hidden"):
                search = search.with_predicate(search.get_category_predicate(".hidden", False))

        if search.is_empty:
            return games

        return [game for game in games if search.matches(game)]

    def set_service(self, service_name):
        if self.service and self.service.id == service_name:
            return self.service
        if not service_name:
            self.service = None
            return
        try:
            self.service = services.SERVICES[service_name]()
        except KeyError:
            logger.error("Non existent service '%s'", service_name)
            self.service = None
        return self.service

    @staticmethod
    def combine_games(service_game, lutris_game):
        """Inject lutris game information into a service game"""
        if lutris_game and service_game["appid"] == lutris_game["service_id"]:
            for field in ("platform", "runner", "year", "installed_at", "lastplayed", "playtime", "installed"):
                service_game[field] = lutris_game[field]
        return service_game

    def get_service_games(self, service_id):
        """Return games for the service indicated."""
        service_games = ServiceGameCollection.get_for_service(service_id)
        if service_id == "lutris":
            lutris_games = {g["slug"]: g for g in games_db.get_games()}
        else:
            lutris_games = {g["service_id"]: g for g in games_db.get_games(filters={"service": self.service.id})}

        return self.filter_games(
            [
                self.combine_games(game, lutris_games.get(game["appid"]))
                for game in self.apply_view_sort(service_games, lambda game: lutris_games.get(game["appid"]) or game)
            ]
        )

    def get_games_from_filters(self):
        service_id = self.filters.get("service")
        if service_id in services.SERVICES:
            if self.service.online and not self.service.is_authenticated():
                self.show_label(_("Connect your %s account to access your games") % self.service.name)
                return []
            return self.get_service_games(service_id)
        if self.filters.get("dynamic_category") in self.dynamic_categories_game_factories:
            return self.dynamic_categories_game_factories[self.filters["dynamic_category"]]()

        search = self.get_game_search()
        category = self.filters.get("category") or "all"
        included = [category] if category != "all" else None
        excluded = [".hidden"] if category != ".hidden" and not search.has_component("hidden") else []
        category_game_ids = categories_db.get_game_ids_for_categories(included, excluded)

        filters = self.get_sql_filters()
        games = games_db.get_games(filters=filters)
        games = self.filter_games([game for game in games if game["id"] in category_game_ids], implicit_filters=False)
        return self.apply_view_sort(games)

    def get_sql_filters(self):
        """Return the current filters for the view"""
        sql_filters = {}
        if self.filters.get("runner"):
            sql_filters["runner"] = self.filters["runner"]
        if self.filters.get("platform"):
            sql_filters["platform"] = self.filters["platform"]
        if self.filters.get("installed") and not self.get_game_search().has_component("installed"):
            sql_filters["installed"] = "1"

        # We omit the "text" search here because SQLite does a fairly literal
        # search, which is accent sensitive. We'll do better with self.filter_games()
        return sql_filters

    def get_service_media(self, icon_type):
        """Return the ServiceMedia class used for this view"""
        service = self.service if self.service else LutrisService
        medias = service.medias
        if icon_type in medias:
            return medias[icon_type]()
        return medias[service.default_format]()

    def update_revealer(self, games=None):
        if games:
            if self.game_bar:
                self.game_bar.destroy()
            if len(games) == 1 and games[0]:
                self.game_bar = GameBar(games[0], self.application, self)
                self.revealer_box.pack_start(self.game_bar, True, True, 0)
            else:
                self.game_bar = None
        elif self.game_bar:
            # The game bar can't be destroyed here because the game gets unselected on Wayland
            # whenever the game bar is interacted with. Instead, we keep the current game bar open
            # when the game gets unselected, which is somewhat closer to what the intended behavior
            # should be anyway. Might require closing the game bar manually in some cases.
            pass
            # self.game_bar.destroy()
        if self.revealer_box.get_children():
            self.game_revealer.set_reveal_child(True)
        else:
            self.game_revealer.set_reveal_child(False)

    def show_empty_label(self):
        """Display a label when the view is empty"""
        filter_text = self.filters.get("text")
        has_uninstalled_games = games_db.get_game_count("installed", "0")
        if filter_text:
            if self.filters.get("category") == "favorite":
                self.show_label(_("Add a game matching '%s' to your favorites to see it here.") % filter_text)
            elif self.filters.get("category") == ".hidden":
                self.show_label(_("No hidden games matching '%s' found.") % filter_text)
            elif self.filters.get("installed") and has_uninstalled_games:
                self.show_label(
                    _("No installed games matching '%s' found. Press Ctrl+I to show uninstalled games.") % filter_text
                )
            else:
                self.show_label(_("No games matching '%s' found ") % filter_text)
        else:
            if self.filters.get("category") == "favorite":
                self.show_label(_("Add games to your favorites to see them here."))
            elif self.filters.get("category") == ".hidden":
                self.show_label(_("No games are hidden."))
            elif self.filters.get("installed") and has_uninstalled_games:
                self.show_label(_("No installed games found. Press Ctrl+I to show uninstalled games."))
            elif (
                not self.filters.get("runner")
                and not self.filters.get("service")
                and not self.filters.get("platform")
                and not self.filters.get("dynamic_category")
            ):
                self.show_splash()
            else:
                self.show_label(_("No games found"))

    def update_store(self) -> None:
        service_id = self.filters.get("service")
        service = self.service
        service_media = self.service_media
        self._game_store_generation += 1
        generation = self._game_store_generation

        def make_game_store(games):
            game_store = GameStore(service, service_media)
            game_store.add_preloaded_games(games, service_id)
            return games, game_store

        def on_games_ready(games, error):
            if generation != self._game_store_generation:
                return  # no longer applicable, we got switched again!

            if error:
                raise error  # bounce any error against the backstop

            # Since get_games_from_filters() seems to be much faster than making a GameStore,
            # we defer the spinner to here, when we know how many games we will show. If there
            # are "many" we show a spinner while the store is built.
            if len(games) > 512:
                self.show_spinner()

            AsyncCall(make_game_store, apply_store, games)

        def apply_store(result, error):
            if generation != self._game_store_generation:
                return  # no longer applicable, we got switched again!

            if error:
                raise error  # bounce any error against the backstop

            games, game_store = result

            if games:
                if len(games) > 1:
                    self.search_entry.set_placeholder_text(_("Search %s games") % len(games))
                else:
                    self.search_entry.set_placeholder_text(_("Search 1 game"))
            else:
                self.search_entry.set_placeholder_text(_("Search games"))

            for view in self.views.values():
                view.service = self.service

            GLib.idle_add(self.update_revealer)
            self.game_store = game_store

            view_type = self.current_view_type

            if view_type in self.views:
                self.current_view = self.views[view_type]
                self.current_view.set_game_store(self.game_store)

            if games:
                self.hide_overlay()
            else:
                self.show_empty_label()

            self.update_notification()

        AsyncCall(self.get_games_from_filters, on_games_ready)

    def _bind_zoom_adjustment(self):
        """Bind the zoom slider to the supported banner sizes"""
        service = self.service if self.service else LutrisService
        media_services = list(service.medias.keys())
        self.load_icon_type()
        self.zoom_adjustment.set_lower(0)
        self.zoom_adjustment.set_upper(len(media_services) - 1)
        if self.icon_type in media_services:
            value = media_services.index(self.icon_type)
        else:
            value = 0
        self.zoom_adjustment.props.value = value
        self.zoom_adjustment.connect("value-changed", self.on_zoom_changed)

    def on_zoom_changed(self, adjustment):
        """Handler for zoom modification"""
        media_index = round(adjustment.props.value)
        adjustment.props.value = media_index
        service = self.service if self.service else LutrisService
        media_services = list(service.medias.keys())
        if len(media_services) <= media_index:
            media_index = media_services.index(service.default_format)
        icon_type = media_services[media_index]
        if icon_type != self.icon_type:
            GLib.idle_add(self.save_icon_type, icon_type)

    def show_label(self, message):
        """Display a label in the middle of the UI"""
        self.show_overlay(Gtk.Label(message, visible=True))

    def show_splash(self):
        theme = "dark" if self.application.style_manager.is_dark else "light"
        side_splash = Gtk.Image(visible=True)
        side_splash.set_from_file(os.path.join(datapath.get(), "media/side-%s.svg" % theme))
        side_splash.set_alignment(0, 0)

        center_splash = Gtk.Image(visible=True)
        center_splash.set_alignment(0.5, 0.5)
        center_splash.set_from_file(os.path.join(datapath.get(), "media/splash-%s.svg" % theme))

        splash_box = Gtk.HBox(visible=True, margin_top=24)
        splash_box.pack_start(side_splash, False, False, 12)
        splash_box.set_center_widget(center_splash)
        splash_box.is_splash = True
        self.show_overlay(splash_box, Gtk.Align.FILL, Gtk.Align.FILL)

    def is_showing_splash(self):
        if self.blank_overlay.get_visible():
            for ch in self.blank_overlay.get_children():
                if hasattr(ch, "is_splash"):
                    return True
        return False

    def show_spinner(self):
        # This is inconsistent, but we can't use the blank overlay for the spinner- it
        # won't reliably start as a child of blank_overlay. It seems like it fails if
        # blank_overlay has never yet been visible.
        # It works better if created up front and shown like this.
        self.game_view_spinner.start()
        self.game_view_spinner.show()
        self.games_stack.hide()
        self.blank_overlay.hide()

    def show_overlay(self, widget, halign=Gtk.Align.FILL, valign=Gtk.Align.FILL):
        """Display a widget in the blank overlay"""
        for child in self.blank_overlay.get_children():
            child.destroy()
        self.blank_overlay.set_halign(halign)
        self.blank_overlay.set_valign(valign)
        self.blank_overlay.add(widget)
        self.blank_overlay.show()
        self.games_stack.hide()
        self.game_view_spinner.hide()

    def hide_overlay(self):
        self.blank_overlay.hide()
        self.game_view_spinner.hide()
        self.games_stack.show()
        for child in self.blank_overlay.get_children():
            child.destroy()

    @property
    def view_type(self):
        """Return the type of view saved by the user"""
        view_type = settings.read_setting("view_type")
        if view_type in ["grid", "list"]:
            return view_type
        return self.default_view_type

    def do_key_press_event(self, event):  # pylint: disable=arguments-differ
        # XXX: This block of code below is to enable searching on type.
        # Enabling this feature steals focus from other entries so it needs
        # some kind of focus detection before enabling library search.

        # Probably not ideal for non-english, but we want to limit
        # which keys actually start searching
        if event.keyval == Gdk.KEY_Escape:
            self.search_entry.set_text("")
            self.current_view.grab_focus()
            return Gtk.ApplicationWindow.do_key_press_event(self, event)

        if (  # pylint: disable=too-many-boolean-expressions
            not Gdk.KEY_0 <= event.keyval <= Gdk.KEY_z
            or event.state & Gdk.ModifierType.CONTROL_MASK
            or event.state & Gdk.ModifierType.SHIFT_MASK
            or event.state & Gdk.ModifierType.META_MASK
            or event.state & Gdk.ModifierType.MOD1_MASK
            or self.search_entry.has_focus()
        ):
            return Gtk.ApplicationWindow.do_key_press_event(self, event)
        self.search_entry.grab_focus()
        return self.search_entry.do_key_press_event(self.search_entry, event)

    def load_icon_type(self):
        """Return the icon style depending on the type of view."""
        default_icon_types = {
            "icon_type_grid": "coverart_med",
        }
        setting_key = "icon_type_%sview" % self.current_view_type
        if self.service and self.service.id != "lutris":
            setting_key += "_%s" % self.service.id
        self.icon_type = settings.read_setting(setting_key, default=default_icon_types.get(setting_key, ""))
        return self.icon_type

    def save_icon_type(self, icon_type):
        """Save icon type to settings"""
        self.icon_type = icon_type
        setting_key = "icon_type_%sview" % self.current_view_type
        if self.service and self.service.id != "lutris":
            setting_key += "_%s" % self.service.id
        settings.write_setting(setting_key, self.icon_type)
        self.redraw_view()

    def redraw_view(self):
        """Completely reconstruct the main view"""
        if not self.game_store:
            logger.error("No game store yet")
            return

        view_type = self.current_view_type

        if view_type not in self.views:
            self.game_store = GameStore(self.service, self.service_media)
            if view_type == "grid":
                self.current_view = GameGridView(
                    self.game_store, hide_text=settings.read_bool_setting("hide_text_under_icons")
                )
            else:
                self.current_view = GameListView(self.game_store)

            self.current_view.connect("game-selected", self.on_game_selection_changed)
            self.current_view.connect("game-activated", self.on_game_activated)
            self.views[view_type] = self.current_view

        scrolledwindow = self.games_stack.get_child_by_name(view_type)

        if not scrolledwindow:
            scrolledwindow = Gtk.ScrolledWindow()
            self.games_stack.add_named(scrolledwindow, view_type)

        if not scrolledwindow.get_child():
            scrolledwindow.add(self.current_view)
            scrolledwindow.show_all()

        self.update_view_settings()
        self.games_stack.set_visible_child_name(view_type)
        self.update_action_state()
        self.update_store()

    def rebuild_view(self, view_type):
        """Discards the view named by 'view_type' and if it is the current view,
        regenerates it. This is used to update view settings that can only be
        set during view construction, and not updated later."""
        if view_type in self.views:
            view = self.views[view_type]
            scrolledwindow = self.games_stack.get_child_by_name(view_type)
            scrolledwindow.remove(view)
            del self.views[view_type]
            if self.current_view_type == view_type:
                self.redraw_view()
            # Because the view has hooks and such hooked up, it must be explicitly
            # destroyed to disconnect everything.
            view.destroy()

    def update_view_settings(self):
        if self.current_view and self.current_view_type == "grid":
            show_badges = settings.read_setting("hide_badges_on_icons") != "True"
            self.current_view.show_badges = show_badges and not bool(self.filters.get("platform"))

    def set_viewtype_icon(self, view_type):
        self.viewtype_icon.set_from_icon_name("view-%s-symbolic" % view_type, Gtk.IconSize.BUTTON)

    def set_show_installed_state(self, filter_installed):
        """Shows or hide uninstalled games"""
        settings.write_setting("filter_installed", bool(filter_installed))
        self.filters["installed"] = filter_installed

    def update_notification(self):
        show_notification = self.is_showing_splash()
        if show_notification:
            if not read_user_info():
                self.lutris_log_in_label.show()
                self.turn_on_library_sync_label.hide()
            elif not settings.read_bool_setting("library_sync_enabled"):
                self.lutris_log_in_label.hide()
                self.turn_on_library_sync_label.show()
            else:
                show_notification = False

        self.login_notification_revealer.set_reveal_child(show_notification)

    @GtkTemplate.Callback
    def on_lutris_log_in_label_activate_link(self, _label, _url):
        ClientLoginDialog(parent=self)

    @GtkTemplate.Callback
    def on_turn_on_library_sync_label_activate_link(self, _label, _url):
        settings.write_setting("library_sync_enabled", True)
        self.sync_library(force=True)
        self.update_notification()

    def on_version_notification_close_button_clicked(self, _button):
        dialog = QuestionDialog(
            {
                "title": _("Unsupported Lutris Version"),
                "question": _(
                    "This version of Lutris will no longer receive support on Github and Discord, "
                    "and may not interoperate properly with Lutris.net. Do you want to use it anyway?"
                ),
                "parent": self,
            }
        )

        if dialog.result == Gtk.ResponseType.YES:
            self.version_notification_revealer.set_reveal_child(False)
            runtime_versions = get_runtime_versions()
            if runtime_versions:
                client_version = runtime_versions.get("client_version")
                settings.write_setting("ignored_supported_lutris_verison", client_version or "")

    def on_service_games_loaded(self, service):
        """Request a view update when service games are loaded"""
        if self.service and service.id == self.service.id:
            self.update_store()
        return True

    def save_window_state(self):
        """Saves the window's size position and state as settings."""
        width, height = self.window_size
        settings.write_setting("width", width)
        settings.write_setting("height", height)
        if self.window_x and self.window_y:
            settings.write_setting("window_x", self.window_x)
            settings.write_setting("window_y", self.window_y)
        settings.write_setting("maximized", self.maximized)

    def restore_window_position(self):
        """Restores the window position only; we call this when showing
        the window, but restore the other settings only when creating it."""
        self.window_x = settings.read_setting("window_x")
        self.window_y = settings.read_setting("window_y")
        if self.window_x and self.window_y:
            self.move(int(self.window_x), int(self.window_y))

    def on_service_login(self, service):
        self.update_notification()
        service.start_reload(self._service_reloaded_cb)
        return True

    def _service_reloaded_cb(self, error):
        if error:
            dialogs.display_error(error, parent=self)

    def on_service_logout(self, service):
        self.update_notification()
        if self.service and service.id == self.service.id:
            self.update_store()
        return True

    def on_lutris_account_connected(self):
        self.update_notification()
        self.sync_library(force=True)

    def on_lutris_account_disconnected(self):
        self.update_notification()

    def on_local_library_updated(self):
        self.redraw_view()

    @GtkTemplate.Callback
    def on_resize(self, widget, *_args):
        """Size-allocate signal.
        Updates stored window size and maximized state.
        """
        if not widget.get_window():
            return
        self.maximized = widget.is_maximized()
        size = widget.get_size()
        if not self.maximized:
            self.window_size = size
        self.search_entry.set_size_request(min(max(50, size[0] - 470), 800), -1)

    def on_window_delete(self, *_args):
        app = self.application
        if app.has_running_games:
            self.hide()
            return True
        if app.has_tray_icon():
            self.hide()
            return True

    def on_visible_changed(self, window, param):
        if self.application.tray:
            self.application.tray.update_present_menu()

    def on_window_configure(self, *_args):
        """Callback triggered when the window is moved, resized..."""
        self.window_x, self.window_y = self.get_position()

    @GtkTemplate.Callback
    def on_destroy(self, *_args):
        """Signal for window close."""
        # Stop cancellable running threads
        for stopper in self.threads_stoppers:
            stopper()

    @GtkTemplate.Callback
    def on_hide(self, *_args):
        self.save_window_state()

    @GtkTemplate.Callback
    def on_show(self, *_args):
        self.restore_window_position()

    @GtkTemplate.Callback
    def on_preferences_activate(self, *_args):
        """Callback when preferences is activated."""
        self.application.show_window(PreferencesDialog, parent=self)

    def on_show_installed_state_change(self, action, value):
        """Callback to handle uninstalled game filter switch"""
        action.set_state(value)
        self.set_show_installed_state(value.get_boolean())
        self.update_store()

    @GtkTemplate.Callback
    def on_search_entry_changed(self, entry):
        """Callback for the search input keypresses"""
        self.search_timer_task.unschedule()
        self.filters["text"] = entry.get_text().strip()
        self.search_timer_task = schedule_at_idle(self.update_store, delay_seconds=0.5)

    @GtkTemplate.Callback
    def on_search_entry_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Down:
            if self.current_view_type == "grid":
                self.current_view.select_path(Gtk.TreePath("0"))  # needed for gridview only
                # if game_bar is alive at this point it can mess grid item selection up
                # for some unknown reason,
                # it is safe to close it here, it will be reopened automatically.
                if self.game_bar:
                    self.game_bar.destroy()  # for gridview only
            self.current_view.set_cursor(Gtk.TreePath("0"), None, False)  # needed for both view types
            self.current_view.grab_focus()

    @GtkTemplate.Callback
    def on_about_clicked(self, *_args):
        """Open the about dialog."""
        dialogs.AboutDialog(parent=self)

    def on_game_unhandled_error(self, _game: Game, error: BaseException) -> None:
        """Called when a game has sent the 'game-error' signal"""

        error_handler = get_error_handler(type(error))
        error_handler(error, self)

    @GtkTemplate.Callback
    def on_add_game_button_clicked(self, *_args):
        """Add a new game manually with the AddGameDialog."""
        self.application.show_window(AddGamesWindow, parent=self)
        return True

    def on_toggle_viewtype(self, *args):
        view_type = "list" if self.current_view_type == "grid" else "grid"
        logger.debug("View type changed to %s", view_type)
        self.set_viewtype_icon(view_type)
        settings.write_setting("view_type", view_type)
        self.redraw_view()
        self._bind_zoom_adjustment()

    def on_icontype_state_change(self, action, value):
        action.set_state(value)
        self._set_icon_type(value.get_string())

    def on_view_sorting_state_change(self, action, value):
        self.actions["view-sorting"].set_state(value)
        value = str(value).strip("'")
        settings.write_setting("view_sorting", value)
        self.update_store()

    def on_view_sorting_direction_change(self, action, value):
        self.actions["view-reverse-order"].set_state(value)
        settings.write_setting("view_reverse_order", bool(value))
        self.update_store()

    def on_view_sorting_installed_first_change(self, action, value):
        self.actions["view-sorting-installed-first"].set_state(value)
        settings.write_setting("view_sorting_installed_first", bool(value))
        self.update_store()

    def on_side_panel_state_change(self, action, value):
        """Callback to handle side panel toggle"""
        action.set_state(value)
        side_panel_visible = value.get_boolean()
        settings.write_setting("side_panel_visible", bool(side_panel_visible))
        self.sidebar_revealer.set_reveal_child(side_panel_visible)

    def on_sidebar_changed(self, widget):
        """Handler called when the selected element of the sidebar changes"""
        for filter_type in ("category", "dynamic_category", "service", "runner", "platform"):
            if filter_type in self.filters:
                self.filters.pop(filter_type)

        row_type, row_id = widget.selected_category
        if row_type == "user_category":
            row_type = "category"
        self.filters[row_type] = row_id

        service_name = self.filters.get("service")
        self.set_service(service_name)
        self._bind_zoom_adjustment()
        self.redraw_view()

        if row_type != "category" or row_id != ".hidden":
            self.sidebar.hidden_row.hide()

        if not MISSING_GAMES.is_initialized or (row_type == "dynamic_category" and row_id == "missing"):
            MISSING_GAMES.update_all_missing()

    def on_game_selection_changed(self, view, selection):
        game_ids = [view.get_game_id_for_path(path) for path in selection]

        if not game_ids:
            GLib.idle_add(self.update_revealer)
            return False

        games = []
        for game_id in game_ids:
            if self.service:
                game = ServiceGameCollection.get_game(self.service.id, game_id)
            else:
                game = games_db.get_game_by_field(game_id, "id")

            # There can be no game found if you are removing a game; it will
            # still have a selected icon in the UI just long enough to get here.
            if game:
                games.append(game)

        GLib.idle_add(self.update_revealer, games)
        return False

    def on_toggle_badges(self, _widget, _data):
        """Event handler to toggle badge visibility"""
        state = settings.read_setting("hide_badges_on_icons").lower() == "true"
        settings.write_setting("hide_badges_on_icons", not state)
        self.on_settings_changed(None, not state, "hide_badges_on_icons")

    def on_settings_changed(self, dialog, state, setting_key):
        if setting_key == "hide_text_under_icons":
            self.rebuild_view("grid")
        else:
            self.update_view_settings()
        self.update_notification()
        return True

    def is_game_displayed(self, game):
        """Return whether a game should be displayed on the view"""
        row = self.sidebar.get_selected_row()

        if row:
            # Stopped games do not get displayed on the running page
            if row.type == "dynamic_category" and row.id == "running" and game.state == game.STATE_STOPPED:
                return False

            # If the update took the row out of this view's category, we'll need
            # to update the view to reflect that.
            search = self.get_game_search()
            enforce_hidden = not search.has_component("hidden")
            if row.type == "dynamic_category" and row.id in ("recent", "missing"):
                if enforce_hidden and ".hidden" in game.get_categories():
                    return False
            elif row.type in ("category", "user_category"):
                categories = game.get_categories()
                if enforce_hidden and row.id != ".hidden" and ".hidden" in categories:
                    return False

                if row.id != "all" and row.id not in categories:
                    return False

        return True

    def on_game_updated(self, game):
        """Updates an individual entry in the view when a game is updated"""
        add_to_path_cache(game)
        self.update_action_state()

        if self.service:
            db_game = self.service.get_service_db_game(game)
        else:
            db_game = games_db.get_game_by_field(game.id, "id")

            if db_game and not self.is_game_displayed(game) and "id" in db_game:
                self.game_store.remove_game(db_game["id"])
                return True

        if db_game:
            updated = self.game_store.update(db_game)
            if not updated:
                self.update_store()

        return True

    def on_game_stopped(self, game: Game) -> None:
        """Updates the game list when a game stops; this keeps the 'running' page updated."""
        selected_row = self.sidebar.get_selected_row()
        # Only update the running page- we lose the selected row when we do this,
        # but on the running page this is okay.
        if selected_row is not None and selected_row.id == "running":
            self.game_store.remove_game(game.id)

    def on_game_installed(self, game):
        self.sync_library()

    def on_game_removed(self):
        """Simple method used to refresh the view"""
        self.sidebar.update_rows()
        self.update_missing_games_sidebar_row()
        self.update_store()
        return True

    def on_game_activated(self, _view, game_id):
        """Handles view activations (double click, enter press)"""
        if self.service:
            logger.debug("Looking up %s game %s", self.service.id, game_id)
            db_game = games_db.get_game_for_service(self.service.id, game_id)

            if db_game and db_game["installed"]:
                game_id = db_game["id"]
            else:
                game_id = self.service.install_by_id(game_id)

        if game_id:
            game = Game(game_id)
            if game.is_installed:
                game.launch(launch_ui_delegate=self)
            else:
                game.install(launch_ui_delegate=self)

    @property
    def download_queue(self) -> DownloadQueue:
        queue = self.download_revealer.get_child()
        if not queue:
            queue = DownloadQueue(self.download_revealer)
            self.download_revealer.add(queue)
        return queue

    def start_runtime_updates(self, force_updates: bool) -> None:
        """Starts the process of applying runtime updates, asynchronously. No UI appears until
        we can determine that there are updates to perform."""

        def create_runtime_updater():
            """This function runs on a worker thread and decides what component updates are
            required; we do this on a thread because it involves hitting the Lutris.net website,
            which can easily block."""
            runtime_updater = RuntimeUpdater(force=force_updates)
            component_updaters = runtime_updater.create_component_updaters()
            supported_client_version = runtime_updater.check_client_versions()
            return component_updaters, runtime_updater, supported_client_version

        def create_runtime_updater_cb(result, error):
            """Picks up the component updates when we know what they are, and begins the installation.
            This must be done on the main thread, since it updates the UI. This would be so much less
            ugly with asyncio, but here we are."""
            if error:
                logger.exception("Failed to obtain updates from Lutris.net: %s", error)
            else:
                component_updaters, runtime_updater, supported_client_version = result

                if supported_client_version:
                    markup = self.version_notification_label.get_label()
                    markup = markup % (settings.VERSION, supported_client_version)
                    self.version_notification_label.set_label(markup)
                    self.version_notification_revealer.set_reveal_child(True)

                if component_updaters:
                    self.install_runtime_component_updates(component_updaters, runtime_updater)
                else:
                    logger.debug("Runtime up to date")

        AsyncCall(create_runtime_updater, create_runtime_updater_cb)

    def install_runtime_component_updates(
        self,
        updaters: List[ComponentUpdater],
        runtime_updater: RuntimeUpdater,
        completion_function: DownloadQueue.CompletionFunction = None,
        error_function: DownloadQueue.ErrorFunction = None,
    ) -> bool:
        """Installs a list of component updates. This displays progress bars
        in the sidebar as it installs updates, one at a time."""

        queue = self.download_queue
        operation_names = [f"component_update:{u.name}" for u in updaters]

        def install_updates():
            for updater in updaters:
                updater.install_update(runtime_updater)
            for updater in updaters:
                updater.join()

        return queue.start_multiple(
            install_updates,
            (u.get_progress for u in updaters),
            completion_function=completion_function,
            error_function=error_function,
            operation_names=operation_names,
        )


def _handle_esynclimiterror(error: EsyncLimitError, parent: Gtk.Window) -> None:
    message = _(
        "Your limits are not set correctly."
        " Please increase them as described here:"
        " <a href='https://github.com/lutris/docs/blob/master/HowToEsync.md'>"
        "How-to:-Esync (https://github.com/lutris/docs/blob/master/HowToEsync.md)</a>"
    )
    ErrorDialog(error, message_markup=message, parent=parent)


register_error_handler(EsyncLimitError, _handle_esynclimiterror)
