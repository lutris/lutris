"""Main window for the Lutris interface."""

# pylint: disable=too-many-lines
# pylint: disable=no-member
import os
from collections import namedtuple
from collections.abc import Callable, Iterable
from gettext import gettext as _
from typing import cast
from urllib.parse import unquote, urlparse

from gi.repository import Gdk, Gio, GLib, Gtk

from lutris import services, settings
from lutris.api import (
    LUTRIS_ACCOUNT_CONNECTED,
    LUTRIS_ACCOUNT_DISCONNECTED,
)
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import saved_searches as saved_searches_db
from lutris.database.categories import CATEGORIES_UPDATED
from lutris.database.saved_searches import SAVED_SEARCHES_UPDATED
from lutris.database.services import ServiceGameCollection
from lutris.exceptions import EsyncLimitError
from lutris.game import (
    GAME_INSTALLED,
    GAME_LAUNCH_STATUS,
    GAME_STOPPED,
    GAME_UNHANDLED_ERROR,
    GAME_UPDATED,
    Game,
)
from lutris.gui import dialogs, game_filter, game_sort, game_source
from lutris.gui.addgameswindow import AddGamesWindow
from lutris.gui.config.edit_saved_search import SearchFiltersBox
from lutris.gui.config.preferences_dialog import PreferencesDialog
from lutris.gui.dialogs import ErrorDialog, get_error_handler, register_error_handler
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate, DialogLaunchUIDelegate
from lutris.gui.dialogs.game_import import ImportGameDialog
from lutris.gui.download_queue import DownloadQueue
from lutris.gui.game_filter import SidebarSelection
from lutris.gui.game_source import GameSourceContext, ViewSortSettings
from lutris.gui.view_state import GameViewState
from lutris.gui.widgets.game_bar import GameBar
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.progress_box import ProgressBox, ProgressInfo
from lutris.gui.widgets.sidebar import LutrisSidebar, SidebarRow
from lutris.gui.widgets.stock_icon_image import StockIconImage
from lutris.gui.widgets.utils import load_icon_theme, open_uri, set_cursor_by_name
from lutris.gui.window.notifications import NotificationMixin
from lutris.gui.window.view_manager import GameViewManager
from lutris.gui.window.window_state import WindowStateMixin
from lutris.runtime import ComponentUpdater, RuntimeUpdater
from lutris.search import GameSearch
from lutris.services.base import SERVICE_GAMES_LOADED, SERVICE_LOGIN, SERVICE_LOGOUT
from lutris.services.lutris import LutrisService, sync_media
from lutris.style_manager import THEME_CHANGED
from lutris.util import datapath
from lutris.util.busy import BUSY_STARTED, BUSY_STOPPED
from lutris.util.jobs import COMPLETED_IDLE_TASK, AsyncCall, schedule_at_idle
from lutris.util.library_sync import LOCAL_LIBRARY_UPDATED, LibrarySyncer
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.path_cache import MISSING_GAMES, add_to_path_cache
from lutris.util.strings import gtk_safe
from lutris.util.system import update_desktop_icons
from lutris.util.wine.wine import clear_wine_version_cache


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "lutris-window.ui"))
class LutrisWindow(
    NotificationMixin,
    WindowStateMixin,
    Gtk.ApplicationWindow,
    DialogLaunchUIDelegate,
    DialogInstallUIDelegate,
):  # type:ignore[misc]
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
    search_filters_button: Gtk.MenuButton = GtkTemplate.Child()
    search_box: Gtk.Box = GtkTemplate.Child()
    zoom_adjustment: Gtk.Adjustment = GtkTemplate.Child()
    blank_overlay: Gtk.Alignment = GtkTemplate.Child()
    viewtype_icon: Gtk.Image = GtkTemplate.Child()
    download_revealer: Gtk.Revealer = GtkTemplate.Child()
    game_view_spinner: Gtk.Spinner = GtkTemplate.Child()
    login_notification_revealer: Gtk.Revealer = GtkTemplate.Child()
    lutris_log_in_label: Gtk.Label = GtkTemplate.Child()
    version_notification_revealer: Gtk.Revealer = GtkTemplate.Child()
    version_notification_label: Gtk.Label = GtkTemplate.Child()
    show_hidden_games_button: Gtk.ModelButton = GtkTemplate.Child()

    def __init__(self, application=None, **kwargs) -> None:
        width = int(settings.read_setting("width") or self.default_width)
        height = int(settings.read_setting("height") or self.default_height)
        super().__init__(
            default_width=width,
            default_height=height,
            window_position=Gtk.WindowPosition.NONE,
            name="lutris",
            icon_name="net.lutris.Lutris",
            application=application,
            **kwargs,
        )
        update_desktop_icons()
        load_icon_theme()
        self.set_wmclass("net.lutris.Lutris", "net.lutris.Lutris")
        self.application = application
        self.window_x, self.window_y = self.get_position()
        self.restore_window_position()
        self.threads_stoppers = []
        self.window_size = (width, height)
        self.maximized = settings.read_setting("maximized") == "True"
        self.service = None
        self.search_timer_task = COMPLETED_IDLE_TASK
        self.view_state = GameViewState(self.load_filters())
        self.set_service(self.view_state.values.service)
        self.icon_type = self.load_icon_type()
        self.view_manager = GameViewManager(self)
        self._is_busy = False
        self._zoom_connected = False

        self.dynamic_categories_game_factories: dict[str, Callable[[], list]] = {
            "recent": self.get_recent_games,
            "missing": self.get_missing_games,
            "running": self.get_running_games,
            ".uncategorized": self.get_uncategorized_games,
        }
        self.sortable_dynamic_categories = game_source.SORTABLE_DYNAMIC_CATEGORIES

        self.accelerators = Gtk.AccelGroup()
        self.add_accel_group(self.accelerators)

        self.connect("delete-event", self.on_window_delete)
        self.connect("configure-event", self.on_window_configure)
        self.connect("realize", self.on_load)
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("notify::visible", self.on_visible_changed)
        if self.maximized:
            self.maximize()
        self.init_template()
        self._init_actions()

        # Per-game progress functions for launch-status (e.g. umu runtime
        # downloads). Keyed by game id so we can retrieve the same function
        # across multiple status updates — DownloadQueue uses the function
        # object itself as the progress box key.
        self._launch_progress_functions: dict[str, ProgressBox.ProgressFunction] = {}

        # Since system-search-symbolic is already *right there* we'll try to pick some
        # other icon for the button that shows the search popover.
        filter_button_image = StockIconImage(
            ["filter-symbolic", "edit-find-replace-symbolic"],
            fallback_name="system-search-symbolic",
            icon_size=Gtk.IconSize.BUTTON,
        )
        filter_button_image.show()
        self.search_filters_button.set_image(filter_button_image)
        self.filter_box_search_name = ""

        # Setup Drag and drop
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_add_uri_targets()

        self.set_viewtype_icon(self.current_view_type)

        lutris_icon = Gtk.Image.new_from_icon_name("net.lutris.Lutris", Gtk.IconSize.MENU)
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

        BUSY_STARTED.register(self.on_busy_started)
        BUSY_STOPPED.register(self.on_busy_stopped)
        SERVICE_LOGIN.register(self.on_service_login)
        SERVICE_LOGOUT.register(self.on_service_logout)
        SERVICE_GAMES_LOADED.register(self.on_service_games_loaded)
        CATEGORIES_UPDATED.register(self.on_categories_updated)
        SAVED_SEARCHES_UPDATED.register(self.on_categories_updated)
        GAME_UPDATED.register(self.on_game_updated)
        GAME_STOPPED.register(self.on_game_stopped)
        GAME_INSTALLED.register(self.on_game_installed)
        GAME_UNHANDLED_ERROR.register(self.on_game_unhandled_error)
        GAME_LAUNCH_STATUS.register(self.on_game_launch_status)
        settings.SETTINGS_CHANGED.register(self.on_settings_changed)
        MISSING_GAMES.updated.register(self.update_missing_games_sidebar_row)
        LUTRIS_ACCOUNT_CONNECTED.register(self.on_lutris_account_connected)
        LUTRIS_ACCOUNT_DISCONNECTED.register(self.on_lutris_account_disconnected)
        LOCAL_LIBRARY_UPDATED.register(self.on_local_library_updated)
        THEME_CHANGED.register(self.on_theme_changed)

        # Finally trigger the initialization of the view here
        selected_category = settings.read_setting("selected_category", default="runner:all")
        self.sidebar.selected_category = selected_category.split(":", maxsplit=1) if selected_category else None

        schedule_at_idle(self.sync_library, delay_seconds=1.0)

    def on_busy_started(self):
        self._is_busy = True
        self.update_busy_cursor()

    def on_busy_stopped(self):
        self._is_busy = False
        self.update_busy_cursor()

    def update_busy_cursor(self):
        """Applies the 'progress' cursor to this window if Lutris is busy. This does nothing
        if the window has not been realized; it can be created but never shown when Lutris is
        started to install or run a game, and it has no GdkWindow to set a cursor on then."""
        set_cursor_by_name(self, "progress" if self._is_busy else None)

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
            "open-search-filters": Action(self.on_open_search_filters),
            "open-forums": Action(lambda *x: open_uri("https://forums.lutris.net/")),
            "open-bug-tracker": Action(lambda *x: open_uri(settings.BUG_TRACKER_URL)),
            "open-discord": Action(lambda *x: open_uri("https://discord.gg/Pnt5CuY")),
            "donate": Action(lambda *x: open_uri("https://lutris.net/donate")),
            "kill-wine": Action(self.on_kill_wine),
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

        def on_library_synced(_result, error):
            """Sync media after the library is loaded"""
            if not error:
                AsyncCall(sync_media, None)

        if settings.read_bool_setting("library_sync_enabled", True):
            AsyncCall(LibrarySyncer().sync_local_library, on_library_synced if force else None, force=force)

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

    @property
    def game_store(self):
        """The store backing the current view; owned by the view manager."""
        return self.view_manager.game_store

    @property
    def current_view(self):
        """The view currently presented (grid or list); owned by the view manager."""
        return self.view_manager.current_view

    @property
    def views(self):
        """The views built so far, keyed by view type; owned by the view manager."""
        return self.view_manager.views

    def on_load(self, widget, data=None):
        """Finish initializing the view"""
        self._bind_zoom_adjustment()
        self.current_view.grab_focus()
        # We could have become busy before we had a GdkWindow to set a cursor on
        self.update_busy_cursor()

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
    def is_show_hidden_sensitive(self) -> bool:
        """True if there are any hidden games to show."""
        return bool(
            self.sidebar.selected_category == ("category", ".hidden")
            or categories_db.get_game_ids_for_categories([".hidden"])
        )

    def on_show_hidden_clicked(self, action, value):
        """Hides or shows the hidden games"""
        hidden_category = "category", ".hidden"
        if self.sidebar.selected_category == hidden_category:
            if self.sidebar.previous_category:
                self.sidebar.selected_category = self.sidebar.previous_category
        else:
            self.sidebar.hidden_row.show()
            self.sidebar.selected_category = hidden_category

    def on_open_search_filters(self, _action, _value):
        def on_filter_popover_closed(_popover):
            self.filter_box_search_name = filter_box.search_name
            self.search_filters_button.set_active(False)

        def on_saved(_box, search_name):
            def switch_to_saved_search():
                self.sidebar.selected_category = "saved_search", search_name
                self.search_entry.set_text("")

            filter_popover.popdown()
            schedule_at_idle(switch_to_saved_search)

        if self.search_filters_button.get_active():
            search = self.get_game_search()
            new_search = saved_searches_db.SavedSearch(0, "", str(search))
            filter_box = SearchFiltersBox(saved_search=new_search, search_entry=self.search_entry)
            filter_box.set_size_request(600, -1)
            if self.filter_box_search_name:
                filter_box.search_name = self.filter_box_search_name
            filter_box.connect("saved", on_saved)
            filter_box.show()
            filter_popover = Gtk.Popover(child=filter_box, can_focus=False, relative_to=self.search_filters_button)
            filter_popover.connect("closed", on_filter_popover_closed)
            filter_popover.popup()

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
    def view_sorting(self) -> str:
        return game_sort.normalize_view_sorting(settings.read_setting("view_sorting"))

    @property
    def view_reverse_order(self) -> bool:
        return settings.read_bool_setting("view_reverse_order", False)

    @property
    def view_sorting_installed_first(self) -> bool:
        return settings.read_bool_setting("view_sorting_installed_first", True)

    @property
    def show_hidden_games(self) -> bool:
        return settings.read_bool_setting("show_hidden_games", False)

    @property
    def is_view_sort_sensitive(self):
        """True if the view sorting options will be effective; most dynamic categories ignore them."""
        return self.view_state.is_sort_sensitive(
            self.dynamic_categories_game_factories, self.sortable_dynamic_categories
        )

    def get_sort_sensitive_columns(self) -> set[int]:
        """Returns the columns of the game store that affect the sort order now, if any."""
        if not self.is_view_sort_sensitive:
            return set()

        return game_sort.get_sort_sensitive_columns(self.view_sorting)

    def get_game_sort_settings(self) -> ViewSortSettings:
        """The view settings that drive sorting, for the game source."""
        return ViewSortSettings(
            self.view_sorting,
            self.view_reverse_order,
            self.view_sorting_installed_first,
        )

    def get_game_source_context(self) -> GameSourceContext:
        """The data needed to list the games of the view, for the game source."""
        return GameSourceContext(
            filters=self.view_state.values,
            search=self.get_game_search(),
            service=self.service,
            sort_settings=self.get_game_sort_settings(),
            running_ids=self.application.get_running_game_ids,
        )

    def apply_view_sort(self, items, resolver=lambda i: i):
        """This sorts a list of items according to the view settings of this window;
        the items can be anything, but you can provide a lambda that provides a
        database game dictionary for each one; this dictionary carries the
        data we sort on (though any field may be missing).

        This sort always sorts installed games ahead of uninstalled ones, even when
        the sort is set to descending.

        This treats 'name' sorting specially, applying a natural sort so that
        'Mega slap battler 20' comes after 'Mega slap battler 3'."""
        return game_source.apply_view_sort(items, self.get_game_source_context(), resolver)

    def get_running_games(self):
        """Return a list of currently running games"""
        return game_source.get_running_games(self.get_game_source_context())

    def get_uncategorized_games(self):
        """Return a list of games not in any category"""
        return game_source.get_uncategorized_games(self.get_game_source_context())

    def get_missing_games(self):
        return game_source.get_missing_games(self.get_game_source_context())

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
        """Return a list of recently played games"""
        return game_source.get_recent_games(self.get_game_source_context())

    def get_game_search(self) -> GameSearch:
        """Returns a game-search object for the current view settings and search text; this object
        is cached so that we need not re-parse the search if it has not changed."""
        return self.view_state.get_game_search(self.service)

    def filter_games(self, games, searches: Iterable[GameSearch] | None = None):
        """Filters a list of games to those matching the searches given; if no searches are given,
        the games are filtered by the filters of the view - the 'installed' and 'text' filters,
        and the hidden games category."""
        if searches is None:
            searches = [game_filter.build_search(self.get_game_search(), self.view_state.values)]

        return game_filter.filter_games(games, searches)

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

    def get_games_from_filters(self):
        """Returns the list of games for the current filters of the view."""
        return game_source.get_games_from_filters(self.get_game_source_context())

    def get_sql_filters(self) -> dict[str, str]:
        """Return the current filters for the view"""
        return game_filter.get_sql_filters(self.view_state.values, self.get_game_search())

    def get_service_media(self, icon_type):
        """Return the ServiceMedia class used for this view"""
        service = self.service if self.service else LutrisService
        medias = service.medias
        if icon_type in medias:
            return medias[icon_type]()
        return medias[service.default_format]()

    def update_revealer(self, games=None):
        if games is not None:  # games can be an empty list!
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
        if self.revealer_box.get_children():
            self.game_revealer.set_reveal_child(True)
        else:
            self.game_revealer.set_reveal_child(False)

    def show_empty_label(self):
        """Display a label when the view is empty, or the splash screen when there is nothing
        to say yet."""
        if self.service and self.service.online and not self.service.is_authenticated():
            self.show_label(_("Connect your %s account to access your games") % self.service.name)
            return

        has_uninstalled_games = bool(games_db.get_game_count("installed", "0"))
        message = game_filter.get_empty_view_message(self.view_state.values, has_uninstalled_games)
        if message is None:
            self.show_splash()
        else:
            self.show_label(message)

    def refresh_view(self):
        self.sidebar.update_rows()
        self.update_missing_games_sidebar_row()
        self.update_store()

    def update_store(self) -> None:
        """Rebuilds the game store in the background; see GameViewManager.update_store."""
        self.view_manager.update_store()

    def _bind_zoom_adjustment(self):
        """Bind the zoom slider to the supported banner sizes"""
        service = self.service if self.service else LutrisService
        icon_type = self.load_icon_type()
        self.zoom_adjustment.set_lower(0)
        self.zoom_adjustment.set_upper(len(service.medias) - 1)

        if icon_type not in service.medias:
            icon_type = service.default_format

        try:
            value = list(service.medias.keys()).index(icon_type)
        except ValueError:
            value = 0

        self.zoom_adjustment.props.value = value
        if not self._zoom_connected:
            # Connect only once; this method is called again when the view or the service
            # changes, and re-connecting would run on_zoom_changed several times per move.
            self.zoom_adjustment.connect("value-changed", self.on_zoom_changed)
            self._zoom_connected = True

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

    def on_theme_changed(self):
        if self.is_showing_splash():
            self.show_splash()

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
            "icon_type_gridview": "coverart_med",
            "icon_type_listview": "banner",
        }
        base_key = "icon_type_%sview" % self.current_view_type
        setting_key = base_key
        if self.service and self.service.id != "lutris":
            setting_key += "_%s" % self.service.id
        self.icon_type = settings.read_setting(setting_key, default=default_icon_types.get(base_key, ""))
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
        """Completely reconstruct the main view; see GameViewManager.redraw_view."""
        self.view_manager.redraw_view()

    def rebuild_view(self, view_type):
        """Discards and regenerates a view; see GameViewManager.rebuild_view."""
        self.view_manager.rebuild_view(view_type)

    def update_view_settings(self):
        self.view_manager.update_view_settings()

    def set_viewtype_icon(self, view_type):
        self.viewtype_icon.set_from_icon_name("view-%s-symbolic" % view_type, Gtk.IconSize.BUTTON)

    def set_show_installed_state(self, filter_installed):
        """Shows or hide uninstalled games"""
        settings.write_setting("filter_installed", bool(filter_installed))
        self.view_state.set_installed(bool(filter_installed))

    def on_service_games_loaded(self, service):
        """Request a view update when service games are loaded."""
        self.view_manager.schedule_update_store()

    def on_categories_updated(self):
        # Called for both categories and saved searches; coalesce the rebuilds into one.
        self.view_manager.schedule_update_store()

    def on_local_library_updated(self):
        self.redraw_view()

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
        self.view_state.set_text(entry.get_text().strip())
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

    def on_kill_wine(self, *_args):
        """Callback to kill all Wine processes after confirmation."""
        dlg = dialogs.QuestionDialog(
            {
                "title": _("Kill all Wine processes"),
                "question": _(
                    "This will kill <b>all</b> Wine processes on the system, "
                    "including any not launched by Lutris.\n\n"
                    "Are you sure you want to continue?"
                ),
                "parent": self,
            }
        )
        if dlg.result == dlg.YES:
            from lutris.util.wine.wine import kill_all_wine_processes  # noqa: PLC0415

            kill_all_wine_processes()

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
        self.save_icon_type(value.get_string())

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
        row_type, row_id = widget.selected_category
        row_type = self.view_state.select_sidebar(row_type, row_id)

        self.set_service(self.view_state.values.service)
        self._bind_zoom_adjustment()
        self.redraw_view()

        if row_type != "category" or row_id != ".hidden":
            self.sidebar.hidden_row.hide()
            self.show_hidden_games_button.set_label(_("Show Hidden Games"))
        else:
            self.show_hidden_games_button.set_label(_("Rehide Hidden Games"))
        # We just _replaced_ the label, need to align it. That is weird and
        # contrary to the docs, but here we are.
        self.show_hidden_games_button.get_child().set_halign(Gtk.Align.START)

        if not MISSING_GAMES.is_initialized or (row_type == "dynamic_category" and row_id == "missing"):
            MISSING_GAMES.update_all_missing()

    def on_game_selection_changed(self, view, selection):
        game_ids = [view.get_game_id_for_path(path) for path in selection]

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

    def on_settings_changed(self, setting_key, new_value, section):
        if section == "lutris" and setting_key == "hide_text_under_icons":
            self.rebuild_view("grid")
        elif section == "services" and setting_key.endswith("_in_games_view"):
            self.view_manager.schedule_update_store()
        else:
            self.update_view_settings()
        self.update_notification()
        return True

    def is_game_displayed(self, game):
        """Return whether a game should be displayed on the view"""
        row = self.sidebar.get_selected_row()

        if not row:
            return True

        # If the search itself includes hidden games, the view does not enforce hiding them.
        enforce_hidden = not self.get_game_search().has_component("hidden")
        selection = SidebarSelection(row.type, row.id)
        return game_filter.is_game_displayed(
            selection, game.get_categories(), game.state == game.STATE_STOPPED, enforce_hidden
        )

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
            updated_columns = self.game_store.update(db_game)
            sensitive_columns = self.get_sort_sensitive_columns()
            if updated_columns is None or not sensitive_columns.isdisjoint(updated_columns):
                self.update_store()

        return True

    def on_game_stopped(self, game: Game) -> None:
        """Updates the game list when a game stops; this keeps the 'running' page updated."""
        selected_row = self.sidebar.get_selected_row()
        # Only update the running page- we lose the selected row when we do this,
        # but on the running page this is okay.
        if isinstance(selected_row, SidebarRow) and selected_row.id == "running":
            self.game_store.remove_game(game.id)
        self._launch_progress_functions.pop(game.id, None)

    def on_game_launch_status(self, game: Game) -> None:
        """Mirror a game's launch_status into the download queue as a pulsing
        progress box — used for umu runtime setup (GE-Proton downloads, etc.)
        so the user has feedback while the game appears stuck in 'Launching'."""
        if not game.launch_status:
            # The progress function will return ProgressInfo.ended() on its
            # next poll, which removes the box; nothing to do here beyond
            # dropping our reference so we don't hang on to stopped games.
            self._launch_progress_functions.pop(game.id, None)
            return

        progress_function = self._launch_progress_functions.get(game.id)
        if progress_function is None:

            def progress_function() -> ProgressInfo:
                if not game.launch_status:
                    return ProgressInfo.ended()
                return ProgressInfo(progress=None, label_markup=gtk_safe(game.launch_status))

            self._launch_progress_functions[game.id] = progress_function

        box = self.download_queue.add_progress_box(progress_function)
        # Force an immediate repaint so the user sees the latest umu message
        # instead of waiting up to 0.5s for the next poll.
        box.update_progress()

    def on_game_installed(self, game):
        self.sync_library()

    def on_game_removed(self):
        """Simple method used to refresh the view"""
        self.refresh_view()
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
    def is_download_queue_empty(self) -> bool:
        """True if the download queue has no active operations, or has not been created yet."""
        queue = cast(DownloadQueue | None, self.download_revealer.get_child())
        return not queue or queue.is_empty

    @property
    def download_queue(self) -> DownloadQueue:
        queue = cast(DownloadQueue, self.download_revealer.get_child())
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

                if supported_client_version and not LINUX_SYSTEM.is_flatpak():
                    markup = _(
                        "Lutris %s is no longer supported. "
                        + '<a href="https://lutris.net/downloads/">Download %s here!</a>'
                    )
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
        updaters: list[ComponentUpdater],
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

            # better safe than sorry - there are Proton builds outside our control
            clear_wine_version_cache()

        def on_complete(result):
            # Downloaded icons may have just landed in the icon theme search path;
            # force a rescan so StockIconImage's "changed" handler re-runs and
            # widgets showing fallbacks pick up the real icons.
            Gtk.IconTheme.get_default().rescan_if_needed()
            if completion_function is not None:
                completion_function(result)

        return queue.start_multiple(
            install_updates,
            (u.get_progress for u in updaters),
            completion_function=on_complete,
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
