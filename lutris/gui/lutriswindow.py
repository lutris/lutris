"""Main window for the Lutris interface."""
# pylint: disable=E0611
import os
import time
from collections import namedtuple

from gi.repository import Gtk, Gdk, GLib, Gio

from lutris import api, pga, settings, shortcuts
from lutris.game import Game
from lutris.sync import sync_from_remote
from lutris.runtime import RuntimeUpdater

from lutris.util import resources
from lutris.util.log import logger
from lutris.util.jobs import AsyncCall
from lutris.util import http
from lutris.util import datapath
from lutris.util import steam
from lutris.util import desktopapps

from lutris.gui import dialogs
from lutris.gui.sidebar import SidebarTreeView
from lutris.gui.logwindow import LogWindow
from lutris.gui.gi_composites import GtkTemplate
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.installgamedialog import InstallerDialog
from lutris.gui.uninstallgamedialog import UninstallGameDialog
from lutris.gui.config_dialogs import (
    AddGameDialog, EditGameConfigDialog, SystemConfigDialog
)
from lutris.gui import flowbox
from lutris.gui.gameviews import (
    GameListView, GameGridView, ContextualMenu, GameStore
)


@GtkTemplate(ui=os.path.join(datapath.get(), 'ui', 'lutris-window.ui'))
class LutrisWindow(Gtk.ApplicationWindow):
    """Handler class for main window signals."""

    __gtype_name__ = 'LutrisWindow'

    main_box = GtkTemplate.Child()
    splash_box = GtkTemplate.Child()
    connect_link = GtkTemplate.Child()
    games_scrollwindow = GtkTemplate.Child()
    sidebar_paned = GtkTemplate.Child()
    sidebar_viewport = GtkTemplate.Child()
    statusbar = GtkTemplate.Child()
    connection_label = GtkTemplate.Child()
    status_box = GtkTemplate.Child()

    def __init__(self, application, **kwargs):
        self.runtime_updater = RuntimeUpdater()
        self.running_game = None
        self.threads_stoppers = []

        # Emulate double click to workaround GTK bug #484640
        # https://bugzilla.gnome.org/show_bug.cgi?id=484640
        self.game_selection_time = 0
        self.game_launch_time = 0
        self.last_selected_game = None
        self.selected_runner = None
        self.selected_platform = None

        # Load settings
        width = int(settings.read_setting('width') or 800)
        height = int(settings.read_setting('height') or 600)
        self.window_size = (width, height)
        self.maximized = settings.read_setting('maximized') == 'True'

        view_type = self.get_view_type()
        self.load_icon_type_from_settings(view_type)
        self.filter_installed = \
            settings.read_setting('filter_installed') == 'true'
        self.sidebar_visible = \
            settings.read_setting('sidebar_visible') in ['true', None]
        self.use_dark_theme = settings.read_setting('dark_theme') == 'true'

        # Sync local lutris library with current Steam games and desktop games
        # before setting up game list and view
        steam.sync_with_lutris()
        desktopapps.sync_with_lutris()

        # Window initialization
        self.game_list = pga.get_games()
        self.game_store = GameStore([], self.icon_type, self.filter_installed)
        self.view = self.get_view(view_type)
        super().__init__(default_width=width,
                         default_height=height,
                         icon_name='lutris',
                         application=application,
                         **kwargs)
        if self.maximized:
            self.maximize()
        self.init_template()
        self._init_actions()

        # Set theme to dark if set in the settings
        self.set_dark_theme(self.use_dark_theme)

        # Load view
        self.games_scrollwindow.add(self.view)
        self.connect_signals()
        self.view.show()

        # Contextual menu
        main_entries = [
            ('play', "Play", self.on_game_run),
            ('install', "Install", self.on_install_clicked),
            ('add', "Add manually", self.on_add_manually),
            ('configure', "Configure", self.on_edit_game_configuration),
            ('browse', "Browse files", self.on_browse_files),
            ('desktop-shortcut', "Create desktop shortcut",
             self.create_desktop_shortcut),
            ('rm-desktop-shortcut', "Delete desktop shortcut",
             self.remove_desktop_shortcut),
            ('menu-shortcut', "Create application menu shortcut",
             self.create_menu_shortcut),
            ('rm-menu-shortcut', "Delete application menu shortcut",
             self.remove_menu_shortcut),
            ('install_more', "Install (add) another version", self.on_install_clicked),
            ('remove', "Remove", self.on_remove_game),
            ('view', "View on Lutris.net", self.on_view_game),
        ]
        self.menu = ContextualMenu(main_entries)
        self.view.contextual_menu = self.menu

        # Sidebar
        self.sidebar_treeview = SidebarTreeView()
        self.sidebar_treeview.connect('cursor-changed', self.on_sidebar_changed)
        self.sidebar_viewport.add(self.sidebar_treeview)
        self.sidebar_treeview.show()

        self.game_store.fill_store(self.game_list)
        self.switch_splash_screen()

        self.show_sidebar()
        self.update_runtime()

        # Connect account and/or sync
        credentials = api.read_api_key()
        if credentials:
            self.on_connect_success(None, credentials)
        else:
            self.toggle_connection(False)
            self.sync_library()

        # Timers
        self.timer_ids = [GLib.timeout_add(300, self.refresh_status)]
        steamapps_paths = steam.get_steamapps_paths(flat=True)
        self.steam_watcher = steam.SteamWatcher(steamapps_paths,
                                                self.on_steam_game_changed)

    def _init_actions(self):
        Action = namedtuple('Action', ('callback', 'type', 'enabled', 'default', 'accel'))
        Action.__new__.__defaults__ = (None, None, True, None, None)

        actions = {
            'browse-games': Action(
                lambda *x: self._open_browser('https://lutris.net/games/')
            ),
            'register-account': Action(
                lambda *x: self._open_browser('https://lutris.net/user/register')
            ),

            'disconnect': Action(self.on_disconnect),
            'connect': Action(self.on_connect),
            'synchronize': Action(lambda *x: self.sync_library()),

            'add-game': Action(self.on_add_game_button_clicked),
            'view-game-log': Action(self.on_view_game_log_activate),

            'stop-game': Action(self.on_game_stop, enabled=False),
            'start-game': Action(self.on_game_run, enabled=False),
            'remove-game': Action(self.on_remove_game, enabled=False),

            'preferences': Action(self.on_preferences_activate),
            'manage-runners': Action(lambda *x: RunnersDialog()),
            'about': Action(self.on_about_clicked),

            'show-installed-only': Action(self.on_show_installed_state_change, type='b',
                                          default=self.filter_installed,
                                          accel='<Primary>h'),
            'view-type': Action(self.on_viewtype_state_change, type='s',
                                default=self.current_view_type),
            'icon-type': Action(self.on_icontype_state_change, type='s',
                                default=self.icon_type),
            'use-dark-theme': Action(self.on_dark_theme_state_change, type='b',
                                     default=self.use_dark_theme),
            'show-side-bar': Action(self.on_sidebar_state_change, type='b',
                                    default=self.sidebar_visible),
        }

        self.actions = {}
        app = self.props.application
        for name, value in actions.items():
            if not value.type:
                action = Gio.SimpleAction.new(name)
                action.connect('activate', value.callback)
            else:
                default_value = None
                param_type = None
                if value.default is not None:
                    default_value = GLib.Variant(value.type, value.default)
                if value.type != 'b':
                    param_type = default_value.get_type()
                action = Gio.SimpleAction.new_stateful(name, param_type, default_value)
                action.connect('change-state', value.callback)
            self.actions[name] = action
            if value.enabled is False:
                action.props.enabled = False
            self.add_action(action)
            if value.accel:
                app.add_accelerator(value.accel, 'win.' + name)

    @property
    def current_view_type(self):
        return 'grid' \
            if self.view.__class__.__name__ == "GameFlowBox" \
            else 'list'

    def on_steam_game_changed(self, operation, path):
        appmanifest = steam.AppManifest(path)
        runner_name = appmanifest.get_runner_name()
        games = pga.get_game_by_field(appmanifest.steamid, field='steamid', all=True)
        if operation == Gio.FileMonitorEvent.DELETED:
            for game in games:
                if game['runner'] == runner_name:
                    steam.mark_as_uninstalled(game)
                    self.view.set_uninstalled(Game(game['id']))
                    break
        elif operation in (Gio.FileMonitorEvent.CHANGED, Gio.FileMonitorEvent.CREATED):
            if not appmanifest.is_installed():
                return
            if runner_name == 'winesteam':
                return
            game_info = None
            for game in games:
                if game['installed'] == 0:
                    game_info = game
                else:
                    # Game is already installed, don't do anything
                    return
            if not game_info:
                game_info = {
                    'name': appmanifest.name,
                    'slug': appmanifest.slug,
                }
            game_id = steam.mark_as_installed(appmanifest.steamid,
                                              runner_name,
                                              game_info)
            game_ids = [game['id'] for game in self.game_list]
            if game_id not in game_ids:
                self.add_game_to_view(game_id)
            else:
                self.view.set_installed(Game(game_id))

    @staticmethod
    def set_dark_theme(is_dark):
        gtksettings = Gtk.Settings.get_default()
        gtksettings.set_property("gtk-application-prefer-dark-theme", is_dark)

    def get_view(self, view_type):
        if view_type == 'grid' and flowbox.FLOWBOX_SUPPORTED:
            return flowbox.GameFlowBox(self.game_list,
                                       icon_type=self.icon_type,
                                       filter_installed=self.filter_installed)
        else:
            return GameListView(self.game_store)

    def connect_signals(self):
        """Connect signals from the view with the main window.

        This must be called each time the view is rebuilt.
        """
        self.view.connect('game-installed', self.on_game_installed)
        self.view.connect("game-activated", self.on_game_run)
        self.view.connect("game-selected", self.game_selection_changed)
        self.view.connect("remove-game", self.on_remove_game)

    @staticmethod
    def check_update():
        """Verify availability of client update."""
        version_request = http.Request('https://lutris.net/version')
        version_request.get()
        version = version_request.content
        if version:
            latest_version = settings.read_setting('latest_version')
            if version > (latest_version or settings.VERSION):
                dialogs.ClientUpdateDialog()
                # Store latest version seen to avoid showing
                # the dialog more than once.
                settings.write_setting('latest_version', version)

    @staticmethod
    def get_view_type():
        if not flowbox.FLOWBOX_SUPPORTED:
            return 'list'
        view_type = settings.read_setting('view_type')
        if view_type in ['grid', 'list']:
            return view_type
        return settings.GAME_VIEW

    def load_icon_type_from_settings(self, view_type):
        """Return the icon style depending on the type of view."""
        if view_type == 'list':
            self.icon_type = settings.read_setting('icon_type_listview')
            default = settings.ICON_TYPE_LISTVIEW
        else:
            self.icon_type = settings.read_setting('icon_type_gridview')
            default = settings.ICON_TYPE_GRIDVIEW
        if self.icon_type not in ("banner_small", "banner", "icon"):
            self.icon_type = default
        return self.icon_type

    def switch_splash_screen(self):
        if len(self.game_list) == 0:
            self.splash_box.show()
            self.sidebar_paned.hide()
            self.games_scrollwindow.hide()
        else:
            self.splash_box.hide()
            self.sidebar_paned.show()
            self.games_scrollwindow.show()

    def switch_view(self, view_type):
        """Switch between grid view and list view."""
        self.view.destroy()
        self.load_icon_type_from_settings(view_type)
        self.game_store.set_icon_type(self.icon_type)

        self.view = self.get_view(view_type)
        self.view.contextual_menu = self.menu
        self.connect_signals()
        scrollwindow_children = self.games_scrollwindow.get_children()
        if len(scrollwindow_children):
            child = scrollwindow_children[0]
            child.destroy()
        self.games_scrollwindow.add(self.view)
        self.set_selected_filter(self.selected_runner, self.selected_platform)
        self.set_show_installed_state(self.filter_installed)
        self.view.show_all()

        settings.write_setting('view_type', view_type)

    def sync_library(self):
        """Synchronize games with local stuff and server."""
        def update_gui(result, error):
            if result:
                added_ids, updated_ids = result
                added_games = pga.get_game_by_field(added_ids, 'id', all=True)
                self.game_list += added_games
                self.view.populate_games(added_games)
                self.switch_splash_screen()
                GLib.idle_add(self.update_existing_games, added_ids, updated_ids, True)
            else:
                logger.error("No results returned when syncing the library")

        self.set_status("Syncing library")
        AsyncCall(sync_from_remote, update_gui)

    def update_existing_games(self, added, updated, first_run=False):
        for game_id in updated.difference(added):
            # XXX this migth not work if the game has no 'item' set
            self.view.update_row(pga.get_game_by_field(game_id, 'id'))

        if first_run:
            icons_sync = AsyncCall(self.sync_icons, callback=None)
            self.threads_stoppers.append(icons_sync.stop_request.set)
            self.set_status("")

    def update_runtime(self):
        self.runtime_updater.update(self.set_status)
        self.threads_stoppers += self.runtime_updater.cancellables

    def sync_icons(self):
        resources.fetch_icons([game['slug'] for game in self.game_list],
                              callback=self.on_image_downloaded)

    def set_status(self, text):
        for child_widget in self.status_box.get_children():
            child_widget.destroy()
        label = Gtk.Label(text)
        label.show()
        self.status_box.add(label)

    def refresh_status(self):
        """Refresh status bar."""
        if self.running_game:
            name = self.running_game.name
            if self.running_game.state == self.running_game.STATE_IDLE:
                self.set_status("Preparing to launch %s" % name)
            elif self.running_game.state == self.running_game.STATE_STOPPED:
                self.set_status("Game has quit")
                self.actions['stop-game'].props.enabled = False
            elif self.running_game.state == self.running_game.STATE_RUNNING:
                self.set_status("Playing %s" % name)
                self.actions['stop-game'].props.enabled = True
        return True

    # ---------
    # Callbacks
    # ---------

    def on_dark_theme_state_change(self, action, value):
        action.set_state(value)
        self.use_dark_theme = value.get_boolean()
        setting_value = 'true' if self.use_dark_theme else 'false'
        settings.write_setting('dark_theme', setting_value)
        self.set_dark_theme(self.use_dark_theme)

    @GtkTemplate.Callback
    def on_connect(self, *args):
        """Callback when a user connects to his account."""
        login_dialog = dialogs.ClientLoginDialog(self)
        login_dialog.connect('connected', self.on_connect_success)
        return True

    def on_connect_success(self, dialog, credentials):
        if isinstance(credentials, str):
            username = credentials
        else:
            username = credentials["username"]
        self.toggle_connection(True, username)
        self.sync_library()
        self.connect_link.hide()
        self.actions['synchronize'].props.enabled = True

    @GtkTemplate.Callback
    def on_disconnect(self, *args):
        api.disconnect()
        self.toggle_connection(False)
        self.connect_link.show()
        self.actions['synchronize'].props.enabled = False

    def toggle_connection(self, is_connected, username=None):
        self.props.application.set_connect_state(is_connected)
        if is_connected:
            connection_status = username
            logger.info('Connected to lutris.net as %s', connection_status)
        else:
            connection_status = "Not connected"
        self.connection_label.set_text(connection_status)

    @staticmethod
    def _open_browser(url):
        Gtk.show_uri(None, url, Gdk.CURRENT_TIME)

    @GtkTemplate.Callback
    def on_resize(self, widget, *args):
        """Size-allocate signal.

        Updates stored window size and maximized state.
        """
        if not widget.get_window():
            return
        self.maximized = widget.is_maximized()
        if not self.maximized:
            self.window_size = widget.get_size()

    @GtkTemplate.Callback
    def on_destroy(self, *args):
        """Signal for window close."""
        # Stop cancellable running threads
        for stopper in self.threads_stoppers:
            stopper()
        self.steam_watcher = None

        if self.running_game \
           and self.running_game.state != self.running_game.STATE_STOPPED:
            logger.info("%s is still running, stopping it", self.running_game.name)
            self.running_game.stop()

        # Save settings
        width, height = self.window_size
        settings.write_setting('width', width)
        settings.write_setting('height', height)
        settings.write_setting('maximized', self.maximized)

    @GtkTemplate.Callback
    def on_preferences_activate(self, *args):
        """Callback when preferences is activated."""
        SystemConfigDialog(parent=self)

    def on_show_installed_state_change(self, action, value):
        action.set_state(value)
        filter_installed = value.get_boolean()
        self.set_show_installed_state(filter_installed)

    def set_show_installed_state(self, filter_installed):
        self.filter_installed = filter_installed
        setting_value = 'true' if filter_installed else 'false'
        settings.write_setting(
            'filter_installed', setting_value
        )
        if self.current_view_type == 'grid':
            self.view.filter_installed = filter_installed
            self.view.invalidate_filter()
        else:
            self.game_store.filter_installed = filter_installed
            self.game_store.modelfilter.refilter()

    @GtkTemplate.Callback
    def on_pga_menuitem_activate(self, *args):
        dialogs.PgaSourceDialog(parent=self)

    @GtkTemplate.Callback
    def on_search_entry_changed(self, widget):
        if self.current_view_type == 'grid':
            self.view.filter_text = widget.get_text()
            self.view.invalidate_filter()
        else:
            self.game_store.filter_text = widget.get_text()
            self.game_store.modelfilter.refilter()

    @GtkTemplate.Callback
    def on_about_clicked(self, *args):
        """Open the about dialog."""
        dialogs.AboutDialog(parent=self)

    def _get_current_game_id(self):
        """Return the id of the current selected game while taking care of the
        double clic bug.
        """
        # Wait two seconds to avoid running a game twice
        if time.time() - self.game_launch_time < 2:
            return
        self.game_launch_time = time.time()
        return self.view.selected_game

    def on_game_run(self, *args, game_id=None):
        """Launch a game, or install it if it is not"""
        if not game_id:
            game_id = self._get_current_game_id()
        if not game_id:
            return
        self.running_game = Game(game_id)
        if self.running_game.is_installed:
            self.running_game.play()
        else:
            game_slug = self.running_game.slug
            self.running_game = None
            InstallerDialog(game_slug, self)

    @GtkTemplate.Callback
    def on_game_stop(self, *args):
        """Stop running game."""
        if self.running_game:
            self.running_game.stop()
            self.actions['stop-game'].props.enabled = False

    def on_install_clicked(self, *args, game_ref=None):
        """Install a game"""
        if not game_ref:
            game_id = self._get_current_game_id()
            game = pga.get_game_by_field(game_id, 'id')
            game_ref = game.get('slug')
            logger.debug("Installing game %s (%s)" % (game_ref, game_id))
        if not game_ref:
            return
        InstallerDialog(game_ref, self)

    def game_selection_changed(self, _widget):
        # Emulate double click to workaround GTK bug #484640
        # https://bugzilla.gnome.org/show_bug.cgi?id=484640
        if type(self.view) is GameGridView:
            is_double_click = time.time() - self.game_selection_time < 0.4
            is_same_game = self.view.selected_game == self.last_selected_game
            if is_double_click and is_same_game:
                self.on_game_run()
            self.game_selection_time = time.time()
            self.last_selected_game = self.view.selected_game

        sensitive = True if self.view.selected_game else False
        self.actions['start-game'].props.enabled = sensitive
        self.actions['remove-game'].props.enabled = sensitive

    def on_game_installed(self, view, game_id):
        if type(game_id) != int:
            raise ValueError("game_id must be an int")
        if not self.view.has_game_id(game_id):
            logger.debug("Adding new installed game to view (%d)" % game_id)
            self.add_game_to_view(game_id, async=False)

        game = Game(game_id)
        view.set_installed(game)
        self.sidebar_treeview.update()
        GLib.idle_add(resources.fetch_icons,
                      [game.slug], self.on_image_downloaded)

    def on_image_downloaded(self, game_slugs):
        for game_slug in game_slugs:
            games = pga.get_game_by_field(game_slug, field='slug', all=True)
            for game in games:
                game = Game(game['id'])
                is_installed = game.is_installed
                self.view.update_image(game.id, is_installed)

    def on_add_manually(self, widget, *args):
        def on_game_added(game):
            self.view.set_installed(game)
            self.sidebar_treeview.update()

        game = Game(self.view.selected_game)
        AddGameDialog(self,
                      game=game,
                      runner=self.selected_runner,
                      callback=lambda: on_game_added(game))

    @GtkTemplate.Callback
    def on_view_game_log_activate(self, *args):
        if not self.running_game:
            dialogs.ErrorDialog('No game log available', parent=self)
            return
        log_title = u"Log for {}".format(self.running_game)
        log_window = LogWindow(log_title, self)
        log_window.logtextview.set_text(self.running_game.game_log)
        log_window.run()
        log_window.destroy()

    @GtkTemplate.Callback
    def on_add_game_button_clicked(self, *args):
        """Add a new game manually with the AddGameDialog."""
        dialog = AddGameDialog(
            self,
            runner=self.selected_runner,
            callback=lambda: self.add_game_to_view(dialog.game.id)
        )
        return True

    def add_game_to_view(self, game_id, async=True):
        if not game_id:
            raise ValueError("Missing game id")

        def do_add_game():
            self.view.add_game_by_id(game_id)
            self.switch_splash_screen()
            self.sidebar_treeview.update()
        if async:
            GLib.idle_add(do_add_game)
        else:
            do_add_game()

    @GtkTemplate.Callback
    def on_remove_game(self, *args):
        selected_game = self.view.selected_game
        UninstallGameDialog(game_id=selected_game,
                            callback=self.remove_game_from_view,
                            parent=self)

    def remove_game_from_view(self, game_id, from_library=False):
        def do_remove_game():
            self.view.remove_game(game_id)
            self.switch_splash_screen()

        if from_library:
            GLib.idle_add(do_remove_game)
        else:
            self.view.update_image(game_id, is_installed=False)
        self.sidebar_treeview.update()

    def on_browse_files(self, widget):
        game = Game(self.view.selected_game)
        path = game.get_browse_dir()
        if path and os.path.exists(path):
            Gtk.show_uri(None, 'file://' + path, Gdk.CURRENT_TIME)
        else:
            dialogs.NoticeDialog(
                "Can't open %s \nThe folder doesn't exist." % path
            )

    def on_view_game(self, widget):
        game = Game(self.view.selected_game)
        self._open_browser('https://lutris.net/games/' + game.slug)

    def on_edit_game_configuration(self, widget):
        """Edit game preferences."""
        game = Game(self.view.selected_game)

        def on_dialog_saved():
            game_id = dialog.game.id
            self.view.remove_game(game_id)
            self.view.add_game_by_id(game_id)
            self.view.set_selected_game(game_id)
            self.sidebar_treeview.update()

        if game.is_installed:
            dialog = EditGameConfigDialog(self, game, on_dialog_saved)

    def on_viewtype_state_change(self, action, val):
        action.set_state(val)
        view_type = val.get_string()
        if view_type != self.current_view_type:
            self.switch_view(view_type)

    def on_icontype_state_change(self, action, value):
        action.set_state(value)
        self.icon_type = value.get_string()
        if self.icon_type == self.game_store.icon_type:
            return
        if self.current_view_type == 'grid':
            settings.write_setting('icon_type_gridview', self.icon_type)
        elif self.current_view_type == 'list':
            settings.write_setting('icon_type_listview', self.icon_type)
        self.game_store.set_icon_type(self.icon_type)
        self.switch_view(self.get_view_type())

    def create_menu_shortcut(self, *args):
        """Add the selected game to the system's Games menu."""
        game = Game(self.view.selected_game)
        shortcuts.create_launcher(game.slug, game.id, game.name, menu=True)

    def create_desktop_shortcut(self, *args):
        """Create a desktop launcher for the selected game."""
        game = Game(self.view.selected_game)
        shortcuts.create_launcher(game.slug, game.id, game.name, desktop=True)

    def remove_menu_shortcut(self, *args):
        game = Game(self.view.selected_game)
        shortcuts.remove_launcher(game.slug, game.id, menu=True)

    def remove_desktop_shortcut(self, *args):
        game = Game(self.view.selected_game)
        shortcuts.remove_launcher(game.slug, game.id, desktop=True)

    def on_sidebar_state_change(self, action, value):
        action.set_state(value)
        self.sidebar_visible = value.get_boolean()
        if self.sidebar_visible:
            settings.write_setting('sidebar_visible', 'true')
        else:
            settings.write_setting('sidebar_visible', 'false')
        self.show_sidebar()

    def show_sidebar(self):
        width = 150 if self.sidebar_visible else 0
        self.sidebar_paned.set_position(width)

    def on_sidebar_changed(self, widget):
        selected_filter = widget.get_selected_filter()
        selected_runner = None
        selected_platform = None
        if not selected_filter:
            pass
        elif selected_filter.startswith('platform:'):
            selected_platform = selected_filter.split(':', 2)[1]
        else:
            selected_runner = selected_filter
        self.set_selected_filter(selected_runner, selected_platform)

    def set_selected_filter(self, runner, platform):
        self.selected_runner = runner
        self.selected_platform = platform
        if self.current_view_type == 'grid':
            self.view.filter_runner = self.selected_runner
            self.view.filter_platform = self.selected_platform
            self.view.invalidate_filter()
        else:
            self.game_store.filter_runner = self.selected_runner
            self.game_store.filter_platform = self.selected_platform
            self.game_store.modelfilter.refilter()
