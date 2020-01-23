"""Main window for the Lutris interface."""
# pylint: disable=no-member
import os
from collections import namedtuple

from gi.repository import Gtk, Gdk, GLib, Gio, GObject

from lutris import api, pga, settings
from lutris.game import Game
from lutris.game_actions import GameActions
from lutris.sync import sync_from_remote
from lutris.gui.installerwindow import InstallerWindow
from lutris.runtime import RuntimeUpdater

from lutris.util.log import logger
from lutris.util.jobs import AsyncCall

from lutris.util import http
from lutris.util import datapath

# from lutris.util.steam.watcher import SteamWatcher

from lutris.services import get_services_synced_at_startup, steam

from lutris.vendor.gi_composites import GtkTemplate

from lutris.gui import dialogs
from lutris.gui.widgets.sidebar import SidebarListBox
from lutris.gui.widgets.services import SyncServiceWindow
from lutris.gui.dialogs.runners import RunnersDialog
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.config.system import SystemConfigDialog
from lutris.gui.views.list import GameListView
from lutris.gui.views.grid import GameGridView
from lutris.gui.views.menu import ContextualMenu
from lutris.gui.views.store import GameStore
from lutris.gui.views.game_panel import GamePanel, GenericPanel
from lutris.gui.widgets.utils import IMAGE_SIZES, open_uri


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "lutris-window.ui"))
class LutrisWindow(Gtk.ApplicationWindow):
    """Handler class for main window signals."""

    default_view_type = "grid"
    default_width = 800
    default_height = 600

    __gtype_name__ = "LutrisWindow"

    main_box = GtkTemplate.Child()
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
    search_spinner = GtkTemplate.Child()
    add_popover = GtkTemplate.Child()
    viewtype_icon = GtkTemplate.Child()
    website_search_toggle = GtkTemplate.Child()

    def __init__(self, application, **kwargs):
        width = int(settings.read_setting("width") or self.default_width)
        height = int(settings.read_setting("height") or self.default_height)
        super().__init__(
            default_width=width,
            default_height=height,
            window_position=Gtk.WindowPosition.NONE,
            icon_name="lutris",
            application=application,
            **kwargs
        )
        self.application = application
        self.runtime_updater = RuntimeUpdater()
        self.threads_stoppers = []
        self.selected_runner = None
        self.selected_platform = None
        self.icon_type = None

        # Load settings
        self.window_size = (width, height)
        self.maximized = settings.read_setting("maximized") == "True"

        view_type = self.get_view_type()
        self.load_icon_type_from_settings(view_type)

        # Window initialization
        self.game_actions = GameActions(application=application, window=self)
        self.search_terms = None
        self.search_timer_id = None
        self.search_mode = "local"
        self.game_store = self.get_store()
        self.view = self.get_view(view_type)

        GObject.add_emission_hook(Game, "game-updated", self.on_game_updated)
        GObject.add_emission_hook(Game, "game-removed", self.on_game_updated)
        GObject.add_emission_hook(Game, "game-started", self.on_game_started)
        GObject.add_emission_hook(
            GenericPanel, "running-game-selected", self.game_selection_changed
        )
        self.connect("delete-event", self.on_window_delete)
        if self.maximized:
            self.maximize()
        self.init_template()
        self._init_actions()
        self._bind_zoom_adjustment()

        # Load view
        self.games_scrollwindow.add(self.view)
        self._connect_signals()
        # Set theme to dark if set in the settings
        self.set_dark_theme()
        self.set_viewtype_icon(view_type)

        # Add additional widgets
        lutris_icon = Gtk.Image.new_from_icon_name("lutris", Gtk.IconSize.MENU)
        lutris_icon.set_margin_right(3)
        self.website_search_toggle.set_image(lutris_icon)
        self.website_search_toggle.set_label("Search Lutris.net")
        self.website_search_toggle.set_tooltip_text("Search Lutris.net")
        self.sidebar_listbox = SidebarListBox()
        self.sidebar_listbox.set_size_request(250, -1)
        self.sidebar_listbox.connect("selected-rows-changed", self.on_sidebar_changed)
        self.sidebar_scrolled.add(self.sidebar_listbox)

        self.game_panel = GenericPanel(application=self.application)

        self.game_scrolled = Gtk.ScrolledWindow(visible=True)
        self.game_scrolled.set_size_request(320, -1)
        self.game_scrolled.get_style_context().add_class("game-scrolled")
        self.game_scrolled.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.EXTERNAL)
        self.game_scrolled.add(self.game_panel)

        self.panel_revealer = Gtk.Revealer(visible=True)
        self.panel_revealer.set_transition_duration(300)
        self.panel_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.panel_revealer.add(self.game_scrolled)

        self.main_box.pack_end(self.panel_revealer, False, False, 0)

        self.view.show()

        self.game_store.load()
        # Contextual menu
        self.view.contextual_menu = ContextualMenu(self.game_actions.get_game_actions())

        # Left/Right Sidebar visibility
        self.sidebar_revealer.set_reveal_child(self.left_side_panel_visible)
        self.sidebar_revealer.set_transition_duration(300)
        self.panel_revealer.set_reveal_child(self.right_side_panel_visible)
        self.panel_revealer.set_transition_duration(300)
        self.update_runtime()

        # Connect account and/or sync
        credentials = api.read_api_key()
        if credentials:
            self.on_connect_success(None, credentials["username"])
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
            "show-left-side-panel": Action(
                self.on_left_side_panel_state_change,
                type="b",
                default=self.left_side_panel_visible,
                accel="F9",
            ),
            "show-hidden-games": Action(
                self.hidden_state_change,
                type="b",
                default=self.show_hidden_games,
            ),
            "show-right-side-panel": Action(
                self.on_right_side_panel_state_change,
                type="b",
                default=self.right_side_panel_visible,
                accel="F10",
            ),
            "open-forums": Action(lambda *x: open_uri("https://forums.lutris.net/")),
            "open-discord": Action(lambda *x: open_uri("https://discord.gg/Pnt5CuY")),
            "donate": Action(lambda *x: open_uri("https://lutris.net/donate")),
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

    def on_hide_game(self, _widget):
        """Add a game to the list of hidden games"""
        game = Game(self.view.selected_game)

        # Append the new hidden ID and save it
        ignores = pga.get_hidden_ids() + [game.id]
        pga.set_hidden_ids(ignores)

        # Update the GUI
        if not self.show_hidden_games:
            self.view.remove_game(game.id)

    def on_unhide_game(self, _widget):
        """Removes a game from the list of hidden games"""
        game = Game(self.view.selected_game)

        # Remove the ID to unhide and save it
        ignores = pga.get_hidden_ids()
        ignores.remove(game.id)
        pga.set_hidden_ids(ignores)

    def hidden_state_change(self, action, value):
        """Hides or shows the hidden games"""
        action.set_state(value)

        # Add or remove hidden games
        ignores = pga.get_hidden_ids()
        settings.write_setting("show_hidden_games",
                               str(self.show_hidden_games).lower(),
                               section="lutris")

        # If we have to show the hidden games now, we need to add them back to
        # the view. If we need to hide them, we just remove them from the view
        if value:
            self.game_store.add_games_by_ids(ignores)
        else:
            for game_id in ignores:
                self.game_store.remove_game(game_id)

    @property
    def current_view_type(self):
        """Returns which kind of view is currently presented (grid or list)"""
        return "grid" if isinstance(self.view, GameGridView) else "list"

    @property
    def filter_installed(self):
        return settings.read_setting("filter_installed").lower() == "true"

    @property
    def left_side_panel_visible(self):
        show_left_panel = (
            settings.read_setting("left_side_panel_visible").lower() != "false"
        )
        return show_left_panel or self.sidebar_visible

    @property
    def right_side_panel_visible(self):
        show_right_panel = (
            settings.read_setting("right_side_panel_visible").lower() != "false"
        )
        return show_right_panel or self.sidebar_visible

    @property
    def sidebar_visible(self):
        """Deprecated: For compability only"""
        return settings.read_setting("sidebar_visible") in [
            "true",
            None,
        ]

    @property
    def use_dark_theme(self):
        """Return whether to use the dark theme variant (if the theme provides one)"""
        return settings.read_setting("dark_theme", default="false").lower() == "true"

    @property
    def show_installed_first(self):
        return (
            settings.read_setting("show_installed_first", default="false").lower()
            == "true"
        )

    def on_tray_icon_toggle(self, action, value):
        """Callback for handling tray icon toggle"""
        action.set_state(value)
        settings.write_setting('show_tray_icon', value)
        self.application.set_tray_icon()

    @property
    def show_tray_icon(self):
        """Setting to hide or show status icon"""
        return settings.read_setting("show_tray_icon", default="false").lower() == "true"

    @property
    def view_sorting(self):
        return settings.read_setting("view_sorting") or "name"

    @property
    def view_sorting_ascending(self):
        return settings.read_setting("view_sorting_ascending").lower() != "false"

    @property
    def show_hidden_games(self):
        return settings.read_setting("show_hidden_games").lower() == "true"

    def get_store(self, games=None):
        """Return an instance of GameStore"""
        games = games or pga.get_games(show_installed_first=self.show_installed_first)
        game_store = GameStore(
            games,
            self.icon_type,
            self.filter_installed,
            self.view_sorting,
            self.view_sorting_ascending,
            self.show_hidden_games,
            self.show_installed_first,
        )
        game_store.connect("sorting-changed", self.on_game_store_sorting_changed)
        return game_store

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
                return
            added_games, removed_games = response

            for game_id in added_games:
                self.game_store.add_or_update(game_id)

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
                    self.game_store.set_uninstalled(Game(game["id"]))
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
                self.game_store.update_game_by_id(game_id)

    def set_dark_theme(self):
        """Enables or disbales dark theme"""
        gtksettings = Gtk.Settings.get_default()
        gtksettings.set_property(
            "gtk-application-prefer-dark-theme", self.use_dark_theme
        )

    def get_view(self, view_type):
        """Return the appropriate widget for the current view"""
        if view_type == "grid":
            return GameGridView(self.game_store)
        return GameListView(self.game_store)

    def _connect_signals(self):
        """Connect signals from the view with the main window.

        This must be called each time the view is rebuilt.
        """

        self.view.connect("game-selected", self.game_selection_changed)
        self.view.connect("game-activated", self.on_game_activated)

    def _bind_zoom_adjustment(self):
        """Bind the zoom slider to the supported banner sizes"""
        image_sizes = list(IMAGE_SIZES.keys())
        self.zoom_adjustment.props.value = image_sizes.index(self.icon_type)
        self.zoom_adjustment.connect(
            "value-changed",
            lambda adj: self._set_icon_type(image_sizes[int(adj.props.value)]),
        )

    def get_view_type(self):
        """Return the type of view saved by the user"""
        view_type = settings.read_setting("view_type")
        if view_type in ["grid", "list"]:
            return view_type
        return self.default_view_type

    def do_key_press_event(self, event):
        if event.keyval == Gdk.KEY_Escape:
            self.search_toggle.set_active(False)
            return Gdk.EVENT_STOP
        # return Gtk.ApplicationWindow.do_key_press_event(self, event)

        # XXX: This block of code below is to enable searching on type.
        # Enabling this feature steals focus from other entries so it needs
        # some kind of focus detection before enabling library search.

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
            default = "icon"
        else:
            self.icon_type = settings.read_setting("icon_type_gridview")
            default = "banner"
        if self.icon_type not in IMAGE_SIZES.keys():
            self.icon_type = default
        return self.icon_type

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

        self.zoom_adjustment.props.value = list(IMAGE_SIZES.keys()).index(
            self.icon_type
        )

        self.set_viewtype_icon(view_type)
        settings.write_setting("view_type", view_type)

    def set_viewtype_icon(self, view_type):
        self.viewtype_icon.set_from_icon_name(
            "view-%s-symbolic" % ("list" if view_type == "grid" else "grid"),
            Gtk.IconSize.BUTTON,
        )

    def sync_library(self):
        """Synchronize games with local stuff and server."""

        def update_gui(result, error):
            self.sync_label.set_label("Synchronize library")
            self.sync_spinner.props.active = False
            self.sync_button.set_sensitive(True)
            if error:
                if isinstance(error, http.UnauthorizedAccess):
                    GLib.idle_add(self.show_invalid_credential_warning)
                else:
                    GLib.idle_add(self.show_library_sync_error)
                return
            if result:
                added_ids, updated_ids = result
                self.game_store.add_games_by_ids(added_ids)
                for game_id in updated_ids.difference(added_ids):
                    self.game_store.update_game_by_id(game_id)
            else:
                logger.error("No results returned when syncing the library")

        self.sync_label.set_label("Synchronizing…")
        self.sync_spinner.props.active = True
        self.sync_button.set_sensitive(False)
        AsyncCall(sync_from_remote, update_gui)

    def open_sync_dialog(self):
        """Opens the service sync dialog"""
        self.add_popover.hide()
        self.application.show_window(SyncServiceWindow)

    def update_runtime(self):
        """Check that the runtime is up to date"""
        runtime_sync = AsyncCall(self.runtime_updater.update, None)
        self.threads_stoppers.append(runtime_sync.stop_request.set)

    def on_dark_theme_state_change(self, action, value):
        """Callback for theme switching action"""
        action.set_state(value)
        settings.write_setting("dark_theme", value.get_boolean())
        self.set_dark_theme()

    @GtkTemplate.Callback
    def on_connect(self, *_args):
        """Callback when a user connects to his account."""
        login_dialog = dialogs.ClientLoginDialog(self)
        login_dialog.connect("connected", self.on_connect_success)
        return True

    def on_connect_success(self, _dialog, username):
        """Callback for user connect success"""
        self.toggle_connection(True, username)
        self.sync_library()
        self.actions["synchronize"].props.enabled = True
        self.actions["register-account"].props.enabled = False

    def on_game_activated(self, _widget, game):
        self.game_selection_changed(None, game)
        if game.is_installed:
            self.application.launch(game)
        else:
            self.application.show_window(InstallerWindow, parent=self, game_slug=game.slug)
            InstallerWindow(
                parent=self, game_slug=game.slug, application=self.application,
            )

    @GtkTemplate.Callback
    def on_disconnect(self, *_args):
        """Callback from user disconnect"""
        dlg = dialogs.QuestionDialog(
            {"question": "Do you want to log out from Lutris?", "title": "Log out?", }
        )
        if dlg.result != Gtk.ResponseType.YES:
            return
        api.disconnect()
        self.toggle_connection(False)
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

    def on_window_delete(self, *_args):
        if self.application.running_games.get_n_items():
            self.hide()
            return True

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
        self.application.show_window(RunnersDialog, transient_for=self)

    def invalidate_game_filter(self):
        """Refilter the game view based on current filters"""
        self.game_store.modelfilter.refilter()
        self.game_store.modelsort.clear_cache()
        self.game_store.sort_view(self.view_sorting, self.view_sorting_ascending)
        self.no_results_overlay.props.visible = not bool(self.game_store.games)

    def on_show_installed_first_state_change(self, action, value):
        """Callback to handle installed games first toggle"""
        action.set_state(value)
        self.set_show_installed_first_state(value.get_boolean())

    def set_show_installed_first_state(self, show_installed_first):
        """Shows the installed games first in the view"""
        settings.write_setting("show_installed_first", bool(show_installed_first))
        self.game_store.sort_view(show_installed_first)
        self.game_store.modelfilter.refilter()

    def on_show_installed_state_change(self, action, value):
        """Callback to handle uninstalled game filter switch"""
        action.set_state(value)
        self.set_show_installed_state(value.get_boolean())

    def set_show_installed_state(self, filter_installed):
        """Shows or hide uninstalled games"""
        settings.write_setting("filter_installed", bool(filter_installed))
        self.game_store.filter_installed = filter_installed
        self.invalidate_game_filter()

    @GtkTemplate.Callback
    def on_search_entry_changed(self, entry):
        """Callback for the search input keypresses"""
        if self.search_mode == "local":
            self.game_store.filter_text = entry.get_text()
            self.invalidate_game_filter()
        elif self.search_mode == "website":
            self.search_spinner.props.active = True
            if self.search_timer_id:
                GLib.source_remove(self.search_timer_id)
            self.search_timer_id = GLib.timeout_add(
                750, self.on_search_games_fire, entry.get_text().lower().strip()
            )
        else:
            raise ValueError("Unsupported search mode %s" % self.search_mode)

    @GtkTemplate.Callback
    def on_search_toggle(self, button):
        """Called when search bar is shown / hidden"""
        active = button.props.active
        self.search_revealer.set_reveal_child(active)
        if active:
            self.search_entry.grab_focus()
        else:
            self.search_entry.props.text = ""

    @GtkTemplate.Callback
    def on_website_search_toggle_toggled(self, toggle_button):
        self.search_terms = self.search_entry.props.text
        if toggle_button.props.active:
            self.search_mode = "website"
            self.search_entry.set_placeholder_text("Search Lutris.net")
            self.search_entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "folder-download-symbolic"
            )
            self.game_store.search_mode = True
            self.search_games(self.search_terms)
        else:
            self.search_mode = "local"
            self.search_entry.set_placeholder_text("Filter the list of games")
            self.search_entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic"
            )
            self.search_games("")
            self.search_spinner.props.active = False

    @GtkTemplate.Callback
    def on_about_clicked(self, *_args):
        """Open the about dialog."""
        dialogs.AboutDialog(parent=self)

    def on_game_error(self, game, error):
        """Called when a game has sent the 'game-error' signal"""
        logger.error("%s crashed", game)
        dialogs.ErrorDialog(error, parent=self)

    def on_game_started(self, game):
        self.game_panel.refresh()
        return True

    def on_game_updated(self, game):
        """Callback to refresh the view when a game is updated"""
        logger.debug("Updating game %s", game)
        if not game.is_installed:
            game = Game(game_id=game.id)
            self.game_selection_changed(None, None)
        game.load_config()
        try:
            self.game_store.update_game_by_id(game.id)
        except ValueError:
            self.game_store.add_game_by_id(game.id)

        self.game_panel.refresh()
        return True

    def on_search_games_fire(self, value):
        GLib.source_remove(self.search_timer_id)
        self.search_timer_id = None
        self.search_games(value)
        return False

    def search_games(self, query):
        """Search for games from the website API"""
        logger.debug("%s search for :%s", self.search_mode, query)
        self.search_terms = query
        self.view.destroy()
        self.game_store = self.get_store(api.search_games(query) if query else None)
        self.game_store.set_icon_type(self.icon_type)
        self.game_store.load(from_search=bool(query))
        self.game_store.filter_text = self.search_entry.props.text
        self.switch_view(self.get_view_type())
        self.invalidate_game_filter()

    def game_selection_changed(self, _widget, game):
        """Callback to handle the selection of a game in the view"""
        child = self.game_scrolled.get_child()
        if child:
            self.game_scrolled.remove(child)
            child.destroy()

        if not game:
            self.game_panel = GenericPanel(application=self.application)
        else:
            self.game_actions.set_game(game=game)
            self.game_panel = GamePanel(self.game_actions)
            self.game_panel.connect("panel-closed", self.on_panel_closed)
            self.view.contextual_menu.connect(
                "shortcut-edited", self.game_panel.on_shortcut_edited
            )
        self.game_scrolled.add(self.game_panel)
        return True

    def on_panel_closed(self, panel):
        self.game_selection_changed(panel, None)

    def update_game(self, slug):
        for pga_game in pga.get_games_where(slug=slug):
            self.game_store.update(pga_game)

    @GtkTemplate.Callback
    def on_add_game_button_clicked(self, *_args):
        """Add a new game manually with the AddGameDialog."""
        self.add_popover.hide()
        AddGameDialog(self, runner=self.selected_runner)
        return True

    def remove_game_from_view(self, game_id, from_library=False):
        """Remove a game from the view"""
        self.game_store.update_game_by_id(game_id)
        self.sidebar_listbox.update()

    def on_toggle_viewtype(self, *args):
        self.switch_view("list" if self.current_view_type == "grid" else "grid")

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
        self.game_store.sort_view(value.get_string(), self.view_sorting_ascending)

    def on_view_sorting_direction_change(self, action, value):
        self.game_store.sort_view(self.view_sorting, value.get_boolean())

    def on_game_store_sorting_changed(self, _game_store, key, ascending):
        self.actions["view-sorting"].set_state(GLib.Variant.new_string(key))
        settings.write_setting("view_sorting", key)

        self.actions["view-sorting-ascending"].set_state(
            GLib.Variant.new_boolean(ascending)
        )
        settings.write_setting("view_sorting_ascending", bool(ascending))

    def on_left_side_panel_state_change(self, action, value):
        """Callback to handle left side panel toggle"""
        action.set_state(value)
        left_side_panel_visible = value.get_boolean()
        settings.write_setting("left_side_panel_visible", bool(left_side_panel_visible))
        self.sidebar_revealer.set_reveal_child(left_side_panel_visible)
        # Retrocompatibility with sidebar_visible :
        # if we change the new attribute, we must set the old one to false
        if self.sidebar_visible:
            settings.write_setting("sidebar_visible", "false")

    def on_right_side_panel_state_change(self, action, value):
        """Callback to handle right side panel toggle"""
        action.set_state(value)
        right_side_panel_visible = value.get_boolean()
        settings.write_setting(
            "right_side_panel_visible", bool(right_side_panel_visible)
        )
        self.panel_revealer.set_reveal_child(right_side_panel_visible)
        self.game_scrolled.set_visible(right_side_panel_visible)
        # Retrocompatibility with sidebar_visible :
        # if we change the new attribute, we must set the old one to false
        if self.sidebar_visible:
            settings.write_setting("sidebar_visible", "false")

    def on_sidebar_changed(self, widget):
        row = widget.get_selected_row()
        if row is None:
            self.set_selected_filter(None, None)
        elif row.type == "runner":
            self.set_selected_filter(row.id, None)
        else:
            self.set_selected_filter(None, row.id)

    def set_selected_filter(self, runner, platform):
        """Filter the view to a given runner and platform"""
        self.selected_runner = runner
        self.selected_platform = platform
        self.game_store.filter_runner = self.selected_runner
        self.game_store.filter_platform = self.selected_platform
        self.invalidate_game_filter()

    def show_invalid_credential_warning(self):
        dialogs.ErrorDialog(
            "Could not connect to your Lutris account. Please sign in again."
        )

    def show_library_sync_error(self):
        dialogs.ErrorDialog(
            "Failed to retrieve game library. "
            "There might be some problems contacting lutris.net"
        )
