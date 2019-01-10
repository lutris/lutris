"""Main window for the Lutris interface."""
# pylint: disable=no-member
import os
import math
from collections import namedtuple
from itertools import chain

from gi.repository import Gtk, Gdk, GLib, Gio

from lutris import api, pga, settings
from lutris.game import Game
from lutris.game_actions import GameActions
from lutris.sync import sync_from_remote
from lutris.runtime import RuntimeUpdater

from lutris.util import resources
from lutris.util.log import logger
from lutris.util.jobs import AsyncCall

from lutris.util import http
from lutris.util import datapath
# from lutris.util.steam.watcher import SteamWatcher

from lutris.services import get_services_synced_at_startup, steam

from lutris.vendor.gi_composites import GtkTemplate

from lutris.gui.util import open_uri
from lutris.gui import dialogs
from lutris.gui.sidebar import SidebarListBox
from lutris.gui.widgets.services import SyncServiceWindow
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.config.system import SystemConfigDialog
from lutris.gui.views.list import GameListView
from lutris.gui.views.grid import GameGridView
from lutris.gui.views.menu import ContextualMenu
from lutris.gui.views.store import GameStore
from lutris.gui.widgets.utils import IMAGE_SIZES
from lutris.gui.game_panel import GamePanel


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "lutris-window.ui"))
class LutrisWindow(Gtk.ApplicationWindow):
    """Handler class for main window signals."""

    __gtype_name__ = "LutrisWindow"

    main_box = GtkTemplate.Child()
    splash_box = GtkTemplate.Child()
    connect_link = GtkTemplate.Child()
    games_scrollwindow = GtkTemplate.Child()
    sidebar_revealer = GtkTemplate.Child()
    sidebar_scrolled = GtkTemplate.Child()
    connection_label = GtkTemplate.Child()
    search_revealer = GtkTemplate.Child()
    search_entry = GtkTemplate.Child()
    search_toggle = GtkTemplate.Child()
    zoom_adjustment = GtkTemplate.Child()
    no_results_overlay = GtkTemplate.Child()
    connect_button = GtkTemplate.Child()
    disconnect_button = GtkTemplate.Child()
    register_button = GtkTemplate.Child()
    sync_button = GtkTemplate.Child()
    sync_label = GtkTemplate.Child()
    sync_spinner = GtkTemplate.Child()
    add_popover = GtkTemplate.Child()
    viewtype_icon = GtkTemplate.Child()

    def __init__(self, application, **kwargs):
        self.application = application
        self.runtime_updater = RuntimeUpdater()
        self.threads_stoppers = []

        # Emulate double click to workaround GTK bug #484640
        # https://bugzilla.gnome.org/show_bug.cgi?id=484640
        self.game_launch_time = 0
        self.selected_runner = None
        self.selected_platform = None
        self.icon_type = None

        # Load settings
        width = int(settings.read_setting("width") or 800)
        height = int(settings.read_setting("height") or 600)
        self.window_size = (width, height)
        self.maximized = settings.read_setting("maximized") == "True"

        view_type = self.get_view_type()
        self.load_icon_type_from_settings(view_type)
        self.filter_installed = settings.read_setting("filter_installed") == "true"
        self.show_installed_first = (
            settings.read_setting("show_installed_first") == "true"
        )
        self.sidebar_visible = settings.read_setting("sidebar_visible") in [
            "true",
            None,
        ]
        self.view_sorting = settings.read_setting("view_sorting") or "name"
        self.view_sorting_ascending = (
            settings.read_setting("view_sorting_ascending") != "false"
        )
        self.use_dark_theme = (
            settings.read_setting("dark_theme", default="false").lower() == "true"
        )
        self.show_tray_icon = (
            settings.read_setting("show_tray_icon", default="false").lower() == "true"
        )

        # Window initialization
        self.game_actions = GameActions(application=application, window=self)
        self.game_list = pga.get_games(show_installed_first=self.show_installed_first)
        self.game_store = GameStore(
            [],
            self.icon_type,
            self.filter_installed,
            self.view_sorting,
            self.view_sorting_ascending,
            self.show_installed_first,
        )
        self.view = self.get_view(view_type)
        self.game_store.connect("sorting-changed", self.on_game_store_sorting_changed)
        super().__init__(
            default_width=width,
            default_height=height,
            icon_name="lutris",
            application=application,
            **kwargs
        )
        if self.maximized:
            self.maximize()
        self.init_template()
        self._init_actions()
        self._bind_zoom_adjustment()

        # Load view
        self.games_scrollwindow.add(self.view)
        self._connect_signals()
        # Set theme to dark if set in the settings
        self.set_dark_theme(self.use_dark_theme)
        self.set_viewtype_icon(view_type)

        # Add additional widgets
        self.sidebar_listbox = SidebarListBox()
        self.sidebar_listbox.set_size_request(250, -1)
        self.sidebar_listbox.connect("selected-rows-changed", self.on_sidebar_changed)
        self.sidebar_scrolled.add(self.sidebar_listbox)

        self.game_revealer = Gtk.Revealer()
        self.game_revealer.show()
        self.game_revealer.set_transition_duration(500)
        self.game_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)

        self.game_scrolled = Gtk.ScrolledWindow()
        self.game_scrolled.set_size_request(320, -1)
        self.game_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self.game_scrolled.show()
        self.game_revealer.add(self.game_scrolled)

        self.game_panel = Gtk.Box()
        self.main_box.pack_end(self.game_revealer, False, False, 0)

        self.view.show()

        # Contextual menu
        self.view.contextual_menu = ContextualMenu(self.game_actions.get_game_actions())

        # Sidebar
        self.game_store.fill_store(self.game_list)
        self.switch_splash_screen()

        self.sidebar_revealer.set_reveal_child(self.sidebar_visible)
        self.update_runtime()

        # Connect account and/or sync
        credentials = api.read_api_key()
        if credentials:
            self.on_connect_success(None, credentials)
        else:
            self.toggle_connection(False)
            self.sync_library()

        self.sync_services()

        # steamapps_paths = steam.get_steamapps_paths(flat=True)
        # self.steam_watcher = SteamWatcher(steamapps_paths, self.on_steam_game_changed)

    def _init_actions(self):
        Action = namedtuple(
            "Action", ("callback", "type", "enabled", "default", "accel")
        )
        Action.__new__.__defaults__ = (None, None, True, None, None)

        actions = {
            "browse-games": Action(lambda *x: open_uri("https://lutris.net/games/")),
            "register-account": Action(
                lambda *x: open_uri("https://lutris.net/user/register/")
            ),
            "disconnect": Action(self.on_disconnect),
            "connect": Action(self.on_connect),
            "synchronize": Action(lambda *x: self.sync_library()),
            "sync-local": Action(lambda *x: self.open_sync_dialog()),
            "add-game": Action(self.on_add_game_button_clicked),
            "preferences": Action(self.on_preferences_activate),
            "manage-runners": Action(self.on_manage_runners),
            "about": Action(self.on_about_clicked),
            "show-installed-only": Action(
                self.on_show_installed_state_change,
                type="b",
                default=self.filter_installed,
                accel="<Primary>h",
            ),
            "show-installed-first": Action(
                self.on_show_installed_first_state_change,
                type="b",
                default=self.show_installed_first,
            ),
            "toggle-viewtype": Action(self.on_toggle_viewtype),
            "icon-type": Action(
                self.on_icontype_state_change, type="s", default=self.icon_type
            ),
            "view-sorting": Action(
                self.on_view_sorting_state_change, type="s", default=self.view_sorting
            ),
            "view-sorting-ascending": Action(
                self.on_view_sorting_direction_change,
                type="b",
                default=self.view_sorting_ascending,
            ),
            "use-dark-theme": Action(
                self.on_dark_theme_state_change, type="b", default=self.use_dark_theme
            ),
            "show-tray-icon": Action(
                self.on_tray_icon_toggle, type="b", default=self.show_tray_icon
            ),
            "show-side-bar": Action(
                self.on_sidebar_state_change,
                type="b",
                default=self.sidebar_visible,
                accel="F9",
            ),
        }

        self.actions = {}
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
            if value.enabled is False:
                action.props.enabled = False
            self.add_action(action)
            if value.accel:
                app.add_accelerator(value.accel, "win." + name)

    @property
    def current_view_type(self):
        """Returns which kind of view is currently presented (grid or list)"""
        return "grid" if isinstance(self.view, GameGridView) else "list"

    def update_games(self, games):
        """Update games from a list of game IDs"""
        game_ids = [game["id"] for game in self.game_list]
        for game_id in games:
            if game_id not in game_ids:
                self.add_game_to_view(game_id)
            else:
                self.view.set_installed(Game(game_id))

    def sync_services(self):
        """Sync local lutris library with current Steam games and desktop games"""
        def full_sync(syncer_cls):
            syncer = syncer_cls()
            games = syncer.load()
            return syncer.sync(games, full=True)

        def on_sync_complete(response, errors):
            """Callback to update the view on sync complete"""
            if errors:
                logger.error("Sync failed: %s", errors)
            added_games, removed_games = response
            self.update_games(added_games)
            for game_id in removed_games:
                self.remove_game_from_view(game_id)

        for service in get_services_synced_at_startup():
            AsyncCall(full_sync, on_sync_complete, service.SYNCER)

    def on_steam_game_changed(self, operation, path):
        """Action taken when a Steam AppManifest file is updated"""
        appmanifest = steam.AppManifest(path)
        # if self.running_game and "steam" in self.running_game.runner_name:
        #     self.running_game.notify_steam_game_changed(appmanifest)

        runner_name = appmanifest.get_runner_name()
        games = pga.get_games_where(steamid=appmanifest.steamid)
        if operation == Gio.FileMonitorEvent.DELETED:
            for game in games:
                if game["runner"] == runner_name:
                    steam.mark_as_uninstalled(game)
                    self.view.set_uninstalled(Game(game["id"]))
                    break
        elif operation in (Gio.FileMonitorEvent.CHANGED, Gio.FileMonitorEvent.CREATED):
            if not appmanifest.is_installed():
                return
            if runner_name == "winesteam":
                return
            game_info = None
            for game in games:
                if game["installed"] == 0:
                    game_info = game
                else:
                    # Game is already installed, don't do anything
                    return
            if not game_info:
                game_info = {"name": appmanifest.name, "slug": appmanifest.slug}
            if steam in get_services_synced_at_startup():
                game_id = steam.mark_as_installed(
                    appmanifest.steamid, runner_name, game_info
                )
                self.update_games([game_id])

    @staticmethod
    def set_dark_theme(is_dark):
        """Enables or disbales dark theme"""
        gtksettings = Gtk.Settings.get_default()
        gtksettings.set_property("gtk-application-prefer-dark-theme", is_dark)

    def get_view(self, view_type):
        """Return the appropriate widget for the current view"""
        if view_type == "grid":
            return GameGridView(self.game_store)
        return GameListView(self.game_store)

    def _connect_signals(self):
        """Connect signals from the view with the main window.

        This must be called each time the view is rebuilt.
        """
        self.connect("delete-event", lambda *x: self.hide_on_delete())
        self.view.connect("game-installed", self.on_game_installed)
        self.view.connect("game-selected", self.game_selection_changed)

    def _bind_zoom_adjustment(self):
        """Bind the zoom slider to the supported banner sizes"""
        image_sizes = list(IMAGE_SIZES.keys())
        self.zoom_adjustment.props.value = image_sizes.index(self.icon_type)
        self.zoom_adjustment.connect(
            "value-changed",
            lambda adj: self._set_icon_type(image_sizes[int(adj.props.value)]),
        )

    @staticmethod
    def check_update():
        """Verify availability of client update."""
        version_request = http.Request("https://lutris.net/version")
        version_request.get()
        version = version_request.content
        if version:
            latest_version = settings.read_setting("latest_version")
            if version > (latest_version or settings.VERSION):
                dialogs.ClientUpdateDialog()
                # Store latest version seen to avoid showing
                # the dialog more than once.
                settings.write_setting("latest_version", version)

    @staticmethod
    def get_view_type():
        """Return the type of view saved by the user"""
        view_type = settings.read_setting("view_type")
        if view_type in ["grid", "list"]:
            return view_type
        return settings.GAME_VIEW

    def do_key_press_event(self, event):
        if event.keyval == Gdk.KEY_Escape:
            self.search_toggle.set_active(False)
            return Gdk.EVENT_STOP

        # Probably not ideal for non-english, but we want to limit
        # which keys actually start searching
        if (
            not Gdk.KEY_0 <= event.keyval <= Gdk.KEY_z
            or event.state & Gdk.ModifierType.CONTROL_MASK
            or event.state & Gdk.ModifierType.SHIFT_MASK
            or event.state & Gdk.ModifierType.META_MASK
            or event.state & Gdk.ModifierType.MOD1_MASK
            or self.search_entry.has_focus()
        ):
            return Gtk.ApplicationWindow.do_key_press_event(self, event)

        self.search_toggle.set_active(True)
        self.search_entry.grab_focus()
        return self.search_entry.do_key_press_event(self.search_entry, event)

    def load_icon_type_from_settings(self, view_type):
        """Return the icon style depending on the type of view."""
        if view_type == "list":
            self.icon_type = settings.read_setting("icon_type_listview")
            default = settings.ICON_TYPE_LISTVIEW
        else:
            self.icon_type = settings.read_setting("icon_type_gridview")
            default = settings.ICON_TYPE_GRIDVIEW
        if self.icon_type not in IMAGE_SIZES.keys():
            self.icon_type = default
        return self.icon_type

    def switch_splash_screen(self, force=None):
        """Toggle the state of the splash screen based on the library contents"""
        if not self.splash_box.get_visible() and self.game_list:
            return
        if self.game_list or force is True:
            self.splash_box.hide()
            self.main_box.show()
            self.games_scrollwindow.show()
        else:
            logger.debug("Showing splash screen")
            self.splash_box.show()
            self.main_box.hide()
            self.games_scrollwindow.hide()

    def switch_view(self, view_type):
        """Switch between grid view and list view."""
        self.view.destroy()
        self.load_icon_type_from_settings(view_type)
        self.game_store.set_icon_type(self.icon_type)

        self.view = self.get_view(view_type)
        self.view.contextual_menu = ContextualMenu(self.game_actions.get_game_actions())
        self._connect_signals()
        scrollwindow_children = self.games_scrollwindow.get_children()
        if scrollwindow_children:
            child = scrollwindow_children[0]
            child.destroy()
        self.games_scrollwindow.add(self.view)
        self.set_selected_filter(self.selected_runner, self.selected_platform)
        self.set_show_installed_state(self.filter_installed)
        self.view.show_all()

        self.zoom_adjustment.props.value = list(IMAGE_SIZES.keys()).index(self.icon_type)

        settings.write_setting("view_type", view_type)

    def set_viewtype_icon(self, view_type):
        self.viewtype_icon.set_from_icon_name(
            "view-%s-symbolic" % "list" if view_type == "grid" else "grid",
            Gtk.IconSize.BUTTON
        )

    def sync_library(self):
        """Synchronize games with local stuff and server."""

        def update_gui(result, error):
            if error:
                logger.error("Failed to synchrone library: %s", error)
                return
            if result:
                added_ids, updated_ids = result

                # sqlite limits the number of query parameters to 999, to
                # bypass that limitation, divide the query in chunks
                size = 999
                added_games = chain.from_iterable(
                    [
                        pga.get_games_where(
                            id__in=list(added_ids)[page * size: page * size + size]
                        )
                        for page in range(math.ceil(len(added_ids) / size))
                    ]
                )
                self.game_list += added_games
                self.switch_splash_screen()
                self.view.populate_games(added_games)
                GLib.idle_add(self.update_existing_games, added_ids, updated_ids, True)
            else:
                logger.error("No results returned when syncing the library")
            self.sync_label.set_label("Synchronize library")
            self.sync_spinner.props.active = False
            self.sync_button.set_sensitive(True)

        self.sync_label.set_label("Synchronizing…")
        self.sync_spinner.props.active = True
        self.sync_button.set_sensitive(False)
        AsyncCall(sync_from_remote, update_gui)

    def open_sync_dialog(self):
        """Opens the service sync dialog"""
        self.add_popover.hide()
        SyncServiceWindow(application=self.application)

    def update_existing_games(self, added, updated, first_run=False):
        """Updates the games in the view from the callback of the method
        Still, working on this docstring.
        If the implementation is shit,  the docstring is as well
        """
        for game_id in updated.difference(added):
            game = pga.get_game_by_field(game_id, "id")
            self.view.update_row(game["id"], game["year"], game["playtime"])

        if first_run:
            self.update_games(added)
            game_slugs = [game["slug"] for game in self.game_list]
            AsyncCall(resources.get_missing_media, self.on_media_returned, game_slugs)

    def on_media_returned(self, lutris_media, _error=None):
        """Called when the Lutris API has provided a list of downloadable media"""
        icons_sync = AsyncCall(resources.fetch_icons, None, lutris_media, self)
        self.threads_stoppers.append(icons_sync.stop_request.set)

    def update_runtime(self):
        """Check that the runtime is up to date"""
        runtime_sync = AsyncCall(self.runtime_updater.update, None)
        self.threads_stoppers.append(runtime_sync.stop_request.set)

    def on_dark_theme_state_change(self, action, value):
        """Callback for theme switching action"""
        action.set_state(value)
        self.use_dark_theme = value.get_boolean()
        setting_value = "true" if self.use_dark_theme else "false"
        settings.write_setting("dark_theme", setting_value)
        self.set_dark_theme(self.use_dark_theme)

    @GtkTemplate.Callback
    def on_connect(self, *_args):
        """Callback when a user connects to his account."""
        login_dialog = dialogs.ClientLoginDialog(self)
        login_dialog.connect("connected", self.on_connect_success)
        return True

    def on_connect_success(self, _dialog, credentials):
        """Callback for user connect success"""
        if isinstance(credentials, str):
            username = credentials
        else:
            username = credentials["username"]
        self.toggle_connection(True, username)
        self.sync_library()
        self.connect_link.set_sensitive(False)
        self.actions["synchronize"].props.enabled = True
        self.actions["register-account"].props.enabled = False

    @GtkTemplate.Callback
    def on_disconnect(self, *_args):
        """Callback from user disconnect"""
        api.disconnect()
        self.toggle_connection(False)
        self.connect_link.show()
        self.actions["synchronize"].props.enabled = False

    def toggle_connection(self, is_connected, username=None):
        """Sets or unset connected state for the current user"""
        self.connect_button.props.visible = not is_connected
        self.register_button.props.visible = not is_connected
        self.disconnect_button.props.visible = is_connected
        self.sync_button.props.visible = is_connected
        if is_connected:
            self.connection_label.set_text(username)
            logger.info("Connected to lutris.net as %s", username)

    @GtkTemplate.Callback
    def on_resize(self, widget, *_args):
        """Size-allocate signal.

        Updates stored window size and maximized state.
        """
        if not widget.get_window():
            return
        self.maximized = widget.is_maximized()
        if not self.maximized:
            self.window_size = widget.get_size()

    @GtkTemplate.Callback
    def on_destroy(self, *_args):
        """Signal for window close."""
        # Stop cancellable running threads
        for stopper in self.threads_stoppers:
            stopper()
        # self.steam_watcher = None

        # Save settings
        width, height = self.window_size
        settings.write_setting("width", width)
        settings.write_setting("height", height)
        settings.write_setting("maximized", self.maximized)

    @GtkTemplate.Callback
    def on_preferences_activate(self, *_args):
        """Callback when preferences is activated."""
        SystemConfigDialog(parent=self)

    @GtkTemplate.Callback
    def on_manage_runners(self, *args):
        return RunnersDialog(transient_for=self)

    def invalidate_game_filter(self):
        """Refilter the game view based on current filters"""
        self.game_store.modelfilter.refilter()
        self.game_store.modelsort.clear_cache()
        self.game_store.sort_view(self.view_sorting, self.view_sorting_ascending)
        self.no_results_overlay.props.visible = len(self.game_store.modelfilter) == 0

    def on_show_installed_first_state_change(self, action, value):
        """Callback to handle installed games first toggle"""
        action.set_state(value)
        show_installed_first = value.get_boolean()
        self.set_show_installed_first_state(show_installed_first)

    def set_show_installed_first_state(self, show_installed_first):
        """Shows the installed games first in the view"""
        self.show_installed_first = show_installed_first
        setting_value = "true" if show_installed_first else "false"
        settings.write_setting("show_installed_first", setting_value)
        self.game_store.sort_view(show_installed_first)
        self.game_store.modelfilter.refilter()

    def on_show_installed_state_change(self, action, value):
        """Callback to handle uninstalled game filter switch"""
        action.set_state(value)
        filter_installed = value.get_boolean()
        self.set_show_installed_state(filter_installed)

    def set_show_installed_state(self, filter_installed):
        """Shows or hide uninstalled games"""
        self.filter_installed = filter_installed
        setting_value = "true" if filter_installed else "false"
        settings.write_setting("filter_installed", setting_value)
        self.game_store.filter_installed = filter_installed
        self.invalidate_game_filter()

    @GtkTemplate.Callback
    def on_pga_menuitem_activate(self, *_args):
        """Callback for opening the PGA dialog"""
        dialogs.PgaSourceDialog(parent=self)

    @GtkTemplate.Callback
    def on_search_entry_changed(self, widget):
        """Callback for the search input keypresses"""
        self.game_store.filter_text = widget.get_text()
        self.invalidate_game_filter()

    @GtkTemplate.Callback
    def on_search_toggle(self, button):
        active = button.props.active
        self.search_revealer.set_reveal_child(active)
        if not active:
            self.search_entry.props.text = ""
        else:
            self.search_entry.grab_focus()

    @GtkTemplate.Callback
    def on_about_clicked(self, *_args):
        """Open the about dialog."""
        dialogs.AboutDialog(parent=self)

    def on_game_error(self, game, error):
        """Called when a game has sent the 'game-error' signal"""
        logger.error("%s crashed", game)
        dialogs.ErrorDialog(error, parent=self)

    def game_selection_changed(self, widget):
        """Callback to handle the selection of a game in the view"""
        child = self.game_scrolled.get_child()
        if child:
            self.game_scrolled.remove(child)
            child.destroy()

        if not self.view.selected_game:
            self.game_revealer.set_reveal_child(False)
            return
        self.game_actions.set_game(game_id=self.view.selected_game)
        self.game_panel = GamePanel(self.game_actions)
        self.game_scrolled.add(self.game_panel)
        self.game_revealer.set_reveal_child(True)

    def on_game_installed(self, view, game_id):
        """Callback to handle newly installed games"""
        if not isinstance(game_id, int):
            raise ValueError("game_id must be an int")
        if not self.view.has_game_id(game_id):
            logger.debug("Adding new installed game to view (%d)", game_id)
            self.add_game_to_view(game_id, is_async=False)

        game = Game(game_id)
        view.set_installed(game)
        self.sidebar_listbox.update()
        GLib.idle_add(resources.fetch_icon, game.slug, self.on_image_downloaded)

    def on_image_downloaded(self, game_slugs, _error=None):
        """Callback for handling successful image downloads"""
        for game_slug in game_slugs:
            self.update_image_for_slug(game_slug)

    def update_image_for_slug(self, slug):
        for pga_game in pga.get_games_where(slug=slug):
            game = Game(pga_game["id"])
            self.view.update_image(game.id, game.is_installed)

    @GtkTemplate.Callback
    def on_add_game_button_clicked(self, *_args):
        """Add a new game manually with the AddGameDialog."""
        self.add_popover.hide()
        dialog = AddGameDialog(
            self,
            runner=self.selected_runner,
            callback=lambda: self.add_game_to_view(dialog.game.id),
        )
        return True

    def add_game_to_view(self, game_id, is_async=True):
        """Add a given game to the current view

        Params:
            game_id (str): SQL ID of the game to add
            is_async (bool): Adds the game asynchronously (defaults to True)
        """
        if not game_id:
            raise ValueError("Missing game id")

        def do_add_game():
            self.view.add_game_by_id(game_id)
            self.switch_splash_screen(force=True)
            self.sidebar_listbox.update()
            return False

        if is_async:
            GLib.idle_add(do_add_game)
        else:
            do_add_game()

    def remove_game_from_view(self, game_id, from_library=False):
        """Remove a game from the view"""

        def do_remove_game():
            self.view.remove_game(game_id)
            self.switch_splash_screen()

        if from_library:
            GLib.idle_add(do_remove_game)
        else:
            self.view.update_image(game_id, is_installed=False)
        self.sidebar_listbox.update()

    def on_toggle_viewtype(self, *args):
        if self.current_view_type == "grid":
            self.switch_view("list")
        else:
            self.switch_view("grid")

    def on_viewtype_state_change(self, action, val):
        """Callback to handle view type switch"""
        action.set_state(val)
        view_type = val.get_string()
        if view_type != self.current_view_type:
            self.switch_view(view_type)

    def _set_icon_type(self, icon_type):
        self.icon_type = icon_type
        if self.icon_type == self.game_store.icon_type:
            return
        if self.current_view_type == "grid":
            settings.write_setting("icon_type_gridview", self.icon_type)
        elif self.current_view_type == "list":
            settings.write_setting("icon_type_listview", self.icon_type)
        self.game_store.set_icon_type(self.icon_type)
        self.switch_view(self.get_view_type())

    def on_icontype_state_change(self, action, value):
        action.set_state(value)
        self._set_icon_type(value.get_string())

    def on_view_sorting_state_change(self, action, value):
        ascending = self.view_sorting_ascending
        self.game_store.sort_view(value.get_string(), ascending)

    def on_view_sorting_direction_change(self, action, value):
        self.game_store.sort_view(self.view_sorting, value.get_boolean())

    def on_game_store_sorting_changed(self, game_store, key, ascending):
        self.view_sorting = key
        self.view_sorting_ascending = ascending
        self.actions["view-sorting"].set_state(GLib.Variant.new_string(key))
        self.actions["view-sorting-ascending"].set_state(
            GLib.Variant.new_boolean(ascending)
        )
        settings.write_setting("view_sorting", self.view_sorting)
        settings.write_setting(
            "view_sorting_ascending", "true" if self.view_sorting_ascending else "false"
        )

    def on_sidebar_state_change(self, action, value):
        """Callback to handle siderbar toggle"""
        action.set_state(value)
        self.sidebar_visible = value.get_boolean()
        setting = "true" if self.sidebar_visible else "false"
        settings.write_setting("sidebar_visible", setting)
        self.sidebar_revealer.set_reveal_child(self.sidebar_visible)

    def on_sidebar_changed(self, widget):
        row = widget.get_selected_row()
        if row is None:
            self.set_selected_filter(None, None)
        elif row.type == "runner":
            self.set_selected_filter(row.id, None)
        else:
            self.set_selected_filter(None, row.id)

    def on_tray_icon_toggle(self, action, value):
        """Callback for handling tray icon toggle"""
        action.set_state(value)
        settings.write_setting("show_tray_icon", value)
        self.application.set_tray_icon(value)

    def set_selected_filter(self, runner, platform):
        """Filter the view to a given runner and platform"""
        self.selected_runner = runner
        self.selected_platform = platform
        self.game_store.filter_runner = self.selected_runner
        self.game_store.filter_platform = self.selected_platform
        self.invalidate_game_filter()
