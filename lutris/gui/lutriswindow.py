"""Main window for the Lutris interface."""
# pylint: disable=E0611
import os
import time
import subprocess

from gi.repository import Gtk, Gdk, GLib, Gio

from lutris import api, pga, runtime, settings, shortcuts
from lutris.game import Game, get_game_list
from lutris.sync import Sync

from lutris.util import display, resources
from lutris.util.log import logger
from lutris.util.jobs import AsyncCall
from lutris.util import datapath
from lutris.util.steam import SteamWatcher, get_steamapps_paths, sync_with_lutris

from lutris.gui import dialogs
from lutris.gui.sidebar import SidebarTreeView
from lutris.gui.logwindow import LogWindow
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.installgamedialog import InstallerDialog
from lutris.gui.uninstallgamedialog import UninstallGameDialog
from lutris.gui.config_dialogs import (
    AddGameDialog, EditGameConfigDialog, SystemConfigDialog
)
from lutris.gui.gameviews import (
    GameListView, GameGridView, ContextualMenu, GameStore
)


def load_view(view, store):
    if view == 'grid':
        view = GameGridView(store)
    elif view == 'list':
        view = GameListView(store)
    return view


class LutrisWindow(Gtk.Application):
    """Handler class for main window signals."""
    def __init__(self, service=None):

        Gtk.Application.__init__(
            self, application_id="net.lutris.main",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        ui_filename = os.path.join(
            datapath.get(), 'ui', 'LutrisWindow.ui'
        )
        if not os.path.exists(ui_filename):
            raise IOError('File %s not found' % ui_filename)

        self.service = service
        self.running_game = None
        self.threads_stoppers = []

        # Emulate double click to workaround GTK bug #484640
        # https://bugzilla.gnome.org/show_bug.cgi?id=484640
        self.game_selection_time = 0
        self.game_launch_time = 0
        self.last_selected_game = None

        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_filename)

        # Load settings
        width = int(settings.read_setting('width') or 800)
        height = int(settings.read_setting('height') or 600)
        self.window_size = (width, height)
        window = self.builder.get_object('window')
        window.resize(width, height)
        view_type = self.get_view_type()
        self.icon_type = self.get_icon_type(view_type)
        filter_installed = \
            settings.read_setting('filter_installed') == 'true'
        self.sidebar_visible = \
            settings.read_setting('sidebar_visible') in ['true', None]

        # Set GTK to prefer dark theme
        gtksettings = Gtk.Settings.get_default()
        gtksettings.set_property("gtk-application-prefer-dark-theme", True)

        # Load view
        logger.debug("Loading view")
        self.game_store = GameStore([], self.icon_type, filter_installed)
        self.view = load_view(view_type, self.game_store)

        logger.debug("Connecting signals")
        self.main_box = self.builder.get_object('main_box')
        self.splash_box = self.builder.get_object('splash_box')
        self.connect_link = self.builder.get_object('connect_link')
        # View menu
        installed_games_only_menuitem =\
            self.builder.get_object('filter_installed')
        installed_games_only_menuitem.set_active(filter_installed)
        self.grid_view_menuitem = self.builder.get_object("gridview_menuitem")
        self.grid_view_menuitem.set_active(view_type == 'grid')
        self.list_view_menuitem = self.builder.get_object("listview_menuitem")
        self.list_view_menuitem.set_active(view_type == 'list')
        sidebar_menuitem = self.builder.get_object('sidebar_menuitem')
        sidebar_menuitem.set_active(self.sidebar_visible)

        # View buttons
        self.grid_view_btn = self.builder.get_object('switch_grid_view_btn')
        self.grid_view_btn.set_active(view_type == 'grid')
        self.list_view_btn = self.builder.get_object('switch_list_view_btn')
        self.list_view_btn.set_active(view_type == 'list')
        # Icon type menu
        self.banner_small_menuitem = \
            self.builder.get_object('banner_small_menuitem')
        self.banner_small_menuitem.set_active(self.icon_type == 'banner_small')
        self.banner_menuitem = self.builder.get_object('banner_menuitem')
        self.banner_menuitem.set_active(self.icon_type == 'banner')
        self.icon_menuitem = self.builder.get_object('icon_menuitem')
        self.icon_menuitem.set_active(self.icon_type == 'icon')

        self.search_entry = self.builder.get_object('search_entry')
        self.search_entry.connect('icon-press', self.on_clear_search)

        # Scroll window
        self.games_scrollwindow = self.builder.get_object('games_scrollwindow')
        self.games_scrollwindow.add(self.view)
        # Status bar
        self.status_label = self.builder.get_object('status_label')
        self.joystick_icons = []
        # Buttons
        self.stop_button = self.builder.get_object('stop_button')
        self.stop_button.set_sensitive(False)
        self.delete_button = self.builder.get_object('delete_button')
        self.delete_button.set_sensitive(False)
        self.play_button = self.builder.get_object('play_button')
        self.play_button.set_sensitive(False)

        # Contextual menu
        main_entries = [
            ('play', "Play", self.on_game_run),
            ('install', "Install", self.on_install_clicked),
            ('add', "Add manually", self.add_manually),
            ('configure', "Configure", self.edit_game_configuration),
            ('browse', "Browse files", self.on_browse_files),
            ('desktop-shortcut', "Create desktop shortcut", self.create_desktop_shortcut),
            ('rm-desktop-shortcut', "Delete desktop shortcut", self.remove_desktop_shortcut),
            ('menu-shortcut', "Create application menu shortcut", self.create_menu_shortcut),
            ('rm-menu-shortcut', "Delete application menu shortcut", self.remove_menu_shortcut),
            ('install_more', "Install (add) another version", self.on_install_clicked),
            ('remove', "Remove", self.on_remove_game),
        ]
        self.menu = ContextualMenu(main_entries)
        self.view.contextual_menu = self.menu

        # Sidebar
        self.sidebar_paned = self.builder.get_object('sidebar_paned')
        self.sidebar_paned.set_position(150)
        self.sidebar_treeview = SidebarTreeView()
        self.sidebar_treeview.connect('cursor-changed', self.on_sidebar_changed)
        self.sidebar_viewport = self.builder.get_object('sidebar_viewport')
        self.sidebar_viewport.add(self.sidebar_treeview)

        # Window initialization
        self.window = self.builder.get_object("window")
        self.window.resize_to_geometry(width, height)
        self.window.show_all()
        if not self.sidebar_visible:
            self.sidebar_viewport.hide()
        self.builder.connect_signals(self)
        self.connect_signals()

        self.statusbar = self.builder.get_object("statusbar")

        # XXX Hide PGA config menu item until it actually gets implemented
        pga_menuitem = self.builder.get_object('pga_menuitem')
        pga_menuitem.hide()

        self.init_game_store()

        sync_with_lutris()

        self.update_runtime()

        # Connect account and/or sync
        credentials = api.read_api_key()
        if credentials:
            self.on_connect_success(None, credentials)
        else:
            self.toggle_connection(False)
            self.sync_library()

        # Timers
        self.timer_ids = [GLib.timeout_add(300, self.refresh_status),
                          GLib.timeout_add(10000, self.on_sync_timer)]
        steamapps_paths = get_steamapps_paths(flat=True)
        self.steam_watcher = SteamWatcher(steamapps_paths, self.on_steam_game_changed)

    def on_steam_game_changed(self, operation, path):
        print "woot woot i'm a callback"
        print operation
        print path

    def init_game_store(self):
        logger.debug("Getting game list")
        game_list = get_game_list()
        self.game_store.fill_store(game_list)
        self.switch_splash_screen()

    @property
    def current_view_type(self):
        return 'grid' \
            if self.view.__class__.__name__ == "GameGridView" \
            else 'list'

    def connect_signals(self):
        """Connect signals from the view with the main window.

        This must be called each time the view is rebuilt.
        """
        self.view.connect('game-installed', self.on_game_installed)
        self.view.connect("game-activated", self.on_game_run)
        self.view.connect("game-selected", self.game_selection_changed)
        self.window.connect("configure-event", self.on_resize)

    def check_update(self):
        """Verify availability of client update."""

        def on_version_received(version, error):
            if not version:
                return
            latest_version = settings.read_setting('latest_version')
            if version > (latest_version or settings.VERSION):
                dialogs.ClientUpdateDialog()
                # Store latest version seen to avoid showing
                # the dialog more than once.
                settings.write_setting('latest_version', version)

        import http  # Move me
        AsyncCall(http.download_content, on_version_received,
                  'https://lutris.net/version')

    def get_view_type(self):
        view_type = settings.read_setting('view_type')
        if view_type in ['grid', 'list']:
            return view_type
        return settings.GAME_VIEW

    def get_icon_type(self, view_type):
        """Return the icon style depending on the type of view."""
        if view_type == 'list':
            icon_type = settings.read_setting('icon_type_listview')
            default = settings.ICON_TYPE_LISTVIEW
        else:
            icon_type = settings.read_setting('icon_type_gridview')
            default = settings.ICON_TYPE_GRIDVIEW
        if icon_type not in ("banner_small", "banner", "icon"):
            icon_type = default
        return icon_type

    def switch_splash_screen(self):
        if not pga.get_table_length():
            self.splash_box.show()
            self.games_scrollwindow.hide()
            self.sidebar_viewport.hide()
        else:
            self.splash_box.hide()
            self.games_scrollwindow.show()
            if self.sidebar_visible:
                self.sidebar_viewport.show()

    def switch_view(self, view_type):
        """Switch between grid view and list view."""
        logger.debug("Switching view")
        if view_type == self.get_view_type():
            return
        self.view.destroy()
        icon_type = self.get_icon_type(view_type)
        self.game_store.set_icon_type(icon_type)

        self.view = load_view(view_type, self.game_store)
        self.view.contextual_menu = self.menu
        self.connect_signals()
        self.games_scrollwindow.add(self.view)
        self.view.show_all()

        # Note: set_active(True *or* False) apparently makes ALL the menuitems
        # in the group send the activate signal...
        if icon_type == 'banner_small':
            self.banner_small_menuitem.set_active(True)
        if icon_type == 'icon':
            self.icon_menuitem.set_active(True)
        if icon_type == 'banner':
            self.banner_menuitem.set_active(True)
        settings.write_setting('view_type', view_type)

    def sync_library(self):
        """Synchronize games with local stuff and server."""
        def update_gui(result, error):
            if result:
                added, updated, installed, uninstalled = result
                self.switch_splash_screen()
                self.game_store.fill_store(added)

                GLib.idle_add(self.update_existing_games,
                              added, updated, installed, uninstalled, True)
            else:
                logger.error("No results returned when syncing the library")

        self.set_status("Syncing library")
        AsyncCall(Sync().sync_all, update_gui)

    def update_existing_games(self, added, updated, installed, uninstalled,
                              first_run=False):
        for game_id in updated.difference(added):
            self.view.update_row(pga.get_game_by_field(game_id, 'id'))

        for game_id in installed.difference(added):
            if not self.view.get_row_by_id(game_id):
                self.view.add_game(game_id)
            self.view.set_installed(Game(game_id))

        for game_id in uninstalled.difference(added):
            self.view.set_uninstalled(game_id)

        if first_run:
            icons_sync = AsyncCall(self.sync_icons, None, stoppable=True)
            self.threads_stoppers.append(icons_sync.stop_request.set)
            self.set_status("Library synced")

    def update_runtime(self):
        cancellables = runtime.update(self.set_status)
        self.threads_stoppers += cancellables

    def sync_icons(self, stop_request=None):
        resources.fetch_icons([game for game in pga.get_games()],
                              callback=self.on_image_downloaded,
                              stop_request=stop_request)

    def set_status(self, text):
        self.status_label.set_text(text)

    def refresh_status(self):
        """Refresh status bar."""
        if self.running_game:
            name = self.running_game.name
            if self.running_game.state == self.running_game.STATE_IDLE:
                self.set_status("Preparing to launch %s" % name)
            elif self.running_game.state == self.running_game.STATE_STOPPED:
                self.set_status("Game has quit")
                display.set_cursor('default', self.window.get_window())
                self.stop_button.set_sensitive(False)
            elif self.running_game.state == self.running_game.STATE_RUNNING:
                self.set_status("Playing %s" % name)
                display.set_cursor('default', self.window.get_window())
                self.stop_button.set_sensitive(True)
        for index in range(4):
            self.joystick_icons.append(
                self.builder.get_object('js' + str(index) + 'image')
            )
            if os.path.exists("/dev/input/js%d" % index):
                self.joystick_icons[index].set_visible(True)
            else:
                self.joystick_icons[index].set_visible(False)
        return True

    def about(self, _widget, _data=None):
        """Open the about dialog."""
        dialogs.AboutDialog(parent=self.window)

    # ---------
    # Callbacks
    # ---------

    def on_clear_search(self, widget, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            widget.set_text('')

    def on_connect(self, *args):
        """Callback when a user connects to his account."""
        login_dialog = dialogs.ClientLoginDialog(self.window)
        login_dialog.connect('connected', self.on_connect_success)
        self.connect_link.hide()

    def on_connect_success(self, dialog, credentials):
        if isinstance(credentials, str):
            username = credentials
        else:
            username = credentials["username"]
        self.toggle_connection(True, username)
        self.sync_library()

    def on_disconnect(self, *args):
        api.disconnect()
        self.toggle_connection(False)
        self.connect_link.show()

    def toggle_connection(self, is_connected, username=None):
        disconnect_menuitem = self.builder.get_object('disconnect_menuitem')
        connect_menuitem = self.builder.get_object('connect_menuitem')
        connection_label = self.builder.get_object('connection_label')

        if is_connected:
            disconnect_menuitem.show()
            connect_menuitem.hide()
            connection_status = "Connected as %s" % username
        else:
            disconnect_menuitem.hide()
            connect_menuitem.show()
            connection_status = "Not connected"
        logger.info(connection_status)
        connection_label.set_text(connection_status)

    def on_register_account(self, *args):
        register_url = "https://lutris.net/user/register"
        try:
            subprocess.check_call(["xdg-open", register_url])
        except subprocess.CalledProcessError:
            Gtk.show_uri(None, register_url, Gdk.CURRENT_TIME)

    def on_synchronize_manually(self, *args):
        """Callback when Synchronize Library is activated."""
        self.sync_library()

    def on_sync_timer(self):
        if (not self.running_game
           or self.running_game.state == Game.STATE_STOPPED):

            def update_gui(result, error):
                if result:
                    self.update_existing_games(set(), set(), *result)
                else:
                    logger.error('No results while syncing local Steam database')
            AsyncCall(Sync().sync_local, update_gui)
        return True

    def on_resize(self, widget, *args):
        """WTF is this doing?"""
        self.window_size = widget.get_size()

    def on_destroy(self, *args):
        """Signal for window close."""
        # Stop cancellable running threads
        for stopper in self.threads_stoppers:
            stopper()

        if self.running_game:
            self.running_game.stop()

        if self.service:
            self.service.stop()

        # Save settings
        width, height = self.window_size
        settings.write_setting('width', width)
        settings.write_setting('height', height)

        Gtk.main_quit(*args)
        logger.debug("Quitting lutris")

    def on_runners_activate(self, _widget, _data=None):
        """Callback when manage runners is activated."""
        RunnersDialog()

    def on_preferences_activate(self, _widget, _data=None):
        """Callback when preferences is activated."""
        SystemConfigDialog()

    def on_show_installed_games_toggled(self, widget, data=None):
        filter_installed = widget.get_active()
        setting_value = 'true' if filter_installed else 'false'
        settings.write_setting(
            'filter_installed', setting_value
        )
        self.game_store.filter_installed = filter_installed
        self.game_store.modelfilter.refilter()

    def on_pga_menuitem_activate(self, _widget, _data=None):
        dialogs.PgaSourceDialog(parent=self.window)

    def on_search_entry_changed(self, widget):
        self.game_store.filter_text = widget.get_text()
        self.game_store.modelfilter.refilter()

    def _get_current_game_id(self):
        """Return the id of the current selected game while taking care of the
        double clic bug.
        """
        # Wait two seconds to avoid running a game twice
        if time.time() - self.game_launch_time < 2:
            return
        self.game_launch_time = time.time()
        return self.view.selected_game

    def on_game_run(self, _widget=None, game_id=None):
        """Launch a game, or install it if it is not"""
        if not game_id:
            game_id = self._get_current_game_id()
        if not game_id:
            return
        display.set_cursor('wait', self.window.get_window())
        self.running_game = Game(game_id)
        if self.running_game.is_installed:
            self.running_game.play()
        else:
            game_slug = self.running_game.slug
            self.running_game = None
            InstallerDialog(game_slug, self)

    def on_game_stop(self, *args):
        """Stop running game."""
        if self.running_game:
            self.running_game.stop()
            self.stop_button.set_sensitive(False)

    def on_install_clicked(self, _widget=None, game_ref=None):
        """Install a game"""
        if not game_ref:
            game_id = self._get_current_game_id()
            game = pga.get_game_by_field(game_id, 'id')
            game_ref = game.get('slug')
            logger.debug("Installing game %s (%s)" % (game_ref, game_id))
        if not game_ref:
            return
        display.set_cursor('wait', self.window.get_window())
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
        self.play_button.set_sensitive(sensitive)
        self.delete_button.set_sensitive(sensitive)

    def on_game_installed(self, view, game_id):
        if type(game_id) != int:
            raise ValueError("game_id must be an int")
        if not self.view.get_row_by_id(game_id):
            logger.debug("Adding new installed game to view (%d)" % game_id)
            self.add_game_to_view(game_id, async=False)

        view.set_installed(Game(game_id))
        self.sidebar_treeview.update()
        game_data = pga.get_game_by_field(game_id, field='id')
        GLib.idle_add(resources.fetch_icons,
                      [game_data], self.on_image_downloaded)

    def on_image_downloaded(self, game_id):
        game = Game(game_id)
        is_installed = game.is_installed
        self.view.update_image(game_id, is_installed)

    def add_manually(self, *args):
        def on_game_added(game):
            self.view.set_installed(game)
            self.sidebar_treeview.update()

        game = Game(self.view.selected_game)
        AddGameDialog(self.window, game, callback=lambda: on_game_added(game))

    def on_view_game_log_activate(self, widget):
        if not self.running_game:
            dialogs.ErrorDialog('No game log available')
            return
        log_title = u"Log for {}".format(self.running_game)
        log_window = LogWindow(log_title, self.window)
        log_window.logtextview.set_text(self.running_game.game_log)
        log_window.run()
        log_window.destroy()

    def add_game(self, _widget, _data=None):
        """Add a new game."""
        dialog = AddGameDialog(
            self.window,
            callback=lambda: self.add_game_to_view(dialog.game.id)
        )

    def add_game_to_view(self, game_id, async=True):
        if not game_id:
            raise ValueError("Missing game id")

        def do_add_game():
            self.view.add_game(game_id)
            self.switch_splash_screen()
            self.sidebar_treeview.update()
        if async:
            GLib.idle_add(do_add_game)
        else:
            do_add_game()

    def on_remove_game(self, _widget, _data=None):
        selected_game = self.view.selected_game
        UninstallGameDialog(game_id=selected_game,
                            callback=self.remove_game_from_view)

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

    def edit_game_configuration(self, _button):
        """Edit game preferences."""
        def on_dialog_saved():
            game_id = dialog.game.id
            self.view.remove_game(game_id)
            self.view.add_game(game_id)
            self.view.set_selected_game(game_id)
            self.sidebar_treeview.update()

        game = Game(self.view.selected_game)
        if game.is_installed:
            dialog = EditGameConfigDialog(self.window, game, on_dialog_saved)

    def on_viewmenu_toggled(self, menuitem):
        view_type = 'grid' if menuitem.get_active() else 'list'
        if view_type == self.current_view_type:
            return
        self.switch_view(view_type)
        self.grid_view_btn.set_active(view_type == 'grid')
        self.list_view_btn.set_active(view_type == 'list')

    def on_viewbtn_toggled(self, widget):
        view_type = 'grid' if widget.get_active() else 'list'
        if view_type == self.current_view_type:
            return
        self.switch_view(view_type)
        self.grid_view_menuitem.set_active(view_type == 'grid')
        self.list_view_menuitem.set_active(view_type == 'list')

    def on_icon_type_activate(self, menuitem):
        icon_type = menuitem.get_name()
        if icon_type == self.game_store.icon_type or not menuitem.get_active():
            return
        if self.current_view_type == 'grid':
            settings.write_setting('icon_type_gridview', icon_type)
        elif self.current_view_type == 'list':
            settings.write_setting('icon_type_listview', icon_type)
        self.game_store.set_icon_type(icon_type)

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

    def toggle_sidebar(self, _widget=None):
        if self.sidebar_visible:
            self.sidebar_paned.remove(self.games_scrollwindow)
            self.main_box.remove(self.sidebar_paned)
            self.main_box.remove(self.statusbar)
            self.main_box.pack_start(self.games_scrollwindow, True, True, 0)
            self.main_box.pack_start(self.statusbar, False, False, 0)
            settings.write_setting('sidebar_visible', 'false')
        else:
            self.main_box.remove(self.games_scrollwindow)
            self.sidebar_paned.add2(self.games_scrollwindow)
            self.main_box.remove(self.statusbar)
            self.main_box.pack_start(self.sidebar_paned, True, True, 0)
            self.main_box.pack_start(self.statusbar, False, False, 0)
            settings.write_setting('sidebar_visible', 'true')
        self.sidebar_visible = not self.sidebar_visible

    def on_sidebar_changed(self, widget):
        self.view.game_store.filter_runner = widget.get_selected_runner()
        self.game_store.modelfilter.refilter()
