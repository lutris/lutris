"""Main window for the Lutris interface."""
# pylint: disable=E0611
import os
import time

from gi.repository import Gtk, Gdk, GLib

from lutris import api, pga, settings, shortcuts
from lutris.game import Game, get_game_list
from lutris.sync import Sync

from lutris.util import runtime
from lutris.util import resources
from lutris.util import system
from lutris.util.log import logger
from lutris.util.jobs import async_call
from lutris.util.strings import slugify
from lutris.util import datapath

from lutris.gui import dialogs
from lutris.gui.sidebar import SidebarTreeView
from lutris.gui.logwindow import LogWindow
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.installgamedialog import InstallerDialog
from lutris.gui.uninstallgamedialog import UninstallGameDialog
from lutris.gui.config_dialogs import (
    AddGameDialog, EditGameConfigDialog, SystemConfigDialog
)
from lutris.gui.widgets import (
    GameListView, GameGridView, ContextualMenu
)


def load_view(view, games=[], filter_text=None, icon_type=None):
    if view == 'grid':
        view = GameGridView(games, filter_text=filter_text,
                            icon_type=icon_type)
    elif view == 'list':
        view = GameListView(games, filter_text=filter_text,
                            icon_type=icon_type)
    return view


class LutrisWindow(object):
    """Handler class for main window signals."""
    def __init__(self):

        ui_filename = os.path.join(
            datapath.get(), 'ui', 'LutrisWindow.ui'
        )
        if not os.path.exists(ui_filename):
            raise IOError('File %s not found' % ui_filename)

        # Currently running game
        self.running_game = None

        # Emulate double click to workaround GTK bug #484640
        # https://bugzilla.gnome.org/show_bug.cgi?id=484640
        self.game_selection_time = 0
        self.game_launch_time = 0
        self.last_selected_game = None

        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_filename)

        # load config
        width = int(settings.read_setting('width') or 800)
        height = int(settings.read_setting('height') or 600)
        self.window_size = (width, height)
        view_type = self.get_view_type()
        self.icon_type = self.get_icon_type(view_type)
        filter_installed_setting = settings.read_setting(
            'filter_installed'
        ) or 'false'
        self.filter_installed = filter_installed_setting == 'true'
        show_installed_games_menuitem = self.builder.get_object(
            'filter_installed'
        )
        show_installed_games_menuitem.set_active(self.filter_installed)
        logger.debug("Getting game list")
        game_list = get_game_list(self.filter_installed)
        logger.debug("Switching view")
        self.view = load_view(view_type, game_list,
                              icon_type=self.icon_type)
        logger.debug("Connecting signals")
        self.main_box = self.builder.get_object('main_box')
        self.splash_box = self.builder.get_object('splash_box')
        # View menu
        self.grid_view_menuitem = self.builder.get_object("gridview_menuitem")
        self.grid_view_menuitem.set_active(view_type == 'grid')
        self.list_view_menuitem = self.builder.get_object("listview_menuitem")
        self.list_view_menuitem.set_active(view_type == 'list')
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
            ('play', "Play", self.on_game_clicked),
            ('install', "Install", self.on_install_clicked),
            ('add', "Add manually", self.add_manually),
            ('configure', "Configure", self.edit_game_configuration),
            ('browse', "Browse files", self.on_browse_files),
            ('desktop-shortcut', "Create desktop shortcut", self.create_desktop_shortcut),
            ('rm-desktop-shortcut', "Delete desktop shortcut", self.remove_desktop_shortcut),
            ('menu-shortcut', "Create application menu shortcut", self.create_menu_shortcut),
            ('rm-menu-shortcut', "Delete application menu shortcut", self.remove_menu_shortcut),
            ('remove', "Remove", self.on_remove_game),
        ]
        self.menu = ContextualMenu(main_entries)
        self.view.contextual_menu = self.menu

        # Timer
        self.timer_id = GLib.timeout_add(2000, self.refresh_status)

        # Sidebar
        sidebar_paned = self.builder.get_object('sidebar_paned')
        sidebar_paned.set_position(150)
        self.sidebar_treeview = SidebarTreeView()
        self.sidebar_treeview.connect('cursor-changed', self.on_sidebar_changed)
        self.sidebar_viewport = self.builder.get_object('sidebar_viewport')
        self.sidebar_viewport.add(self.sidebar_treeview)

        # Window initialization
        self.window = self.builder.get_object("window")
        self.window.resize_to_geometry(width, height)
        self.window.show_all()
        self.builder.connect_signals(self)
        self.connect_signals()

        # XXX Hide PGA config menu item until it actually gets implemented
        pga_menuitem = self.builder.get_object('pga_menuitem')
        pga_menuitem.hide()

        self.switch_splash_screen()

        # Connect account and/or sync
        credentials = api.read_api_key()
        if credentials:
            self.on_connect_success(None, credentials)
        else:
            self.toggle_connection(False)
            sync = Sync()
            async_call(
                sync.sync_steam_local,
                lambda r, e: async_call(self.sync_icons, None),
                caller=self
            )
        # Update Runtime
        async_call(runtime.update_runtime, None, self.set_status)

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
        self.view.connect("game-activated", self.on_game_clicked)
        self.view.connect("game-selected", self.game_selection_changed)
        self.window.connect("configure-event", self.on_resize)
        self.window.connect("key-press-event", self.on_keypress)

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
        if self.view.n_games == 0:
            self.splash_box.show()
            self.games_scrollwindow.hide()
            self.sidebar_viewport.hide()
        else:
            self.splash_box.hide()
            self.games_scrollwindow.show()

    def switch_view(self, view_type):
        """Switch between grid view and list view."""
        logger.debug("Switching view")
        self.icon_type = self.get_icon_type(view_type)
        self.view.destroy()
        self.view = load_view(
            view_type,
            get_game_list(filter_installed=self.filter_installed),
            filter_text=self.search_entry.get_text(),
            icon_type=self.icon_type
        )
        self.view.contextual_menu = self.menu
        self.connect_signals()
        self.games_scrollwindow.add(self.view)
        self.view.show_all()
        self.view.check_resize()
        # Note: set_active(True *or* False) apparently makes ALL the menuitems
        # in the group send the activate signal...
        if self.icon_type == 'banner_small':
            self.banner_small_menuitem.set_active(True)
        if self.icon_type == 'icon':
            self.icon_menuitem.set_active(True)
        if self.icon_type == 'banner':
            self.banner_menuitem.set_active(True)

    def sync_library(self):
        def set_library_synced(result, error):
            self.set_status("Library synced")
            self.switch_splash_screen()
            self.sidebar_treeview.update()
        self.set_status("Syncing library")
        sync = Sync()
        async_call(
            sync.sync_all,
            lambda r, e: async_call(self.sync_icons, set_library_synced),
            caller=self
        )

    def sync_icons(self):
        game_list = pga.get_games()
        resources.fetch_icons([game_info['slug'] for game_info in game_list],
                              callback=self.on_image_downloaded)

    def set_status(self, text):
        self.status_label.set_text(text)

    def refresh_status(self):
        """Refresh status bar."""
        if self.running_game:
            name = self.running_game.name
            if self.running_game.state == self.running_game.STATE_IDLE:
                self.status_label.set_text("Preparing to launch %s" % name)
            elif self.running_game.state == self.running_game.STATE_STOPPED:
                self.status_label.set_text("Game has quit")
                self.stop_button.set_sensitive(False)
            elif self.running_game.state == self.running_game.STATE_RUNNING:
                self.status_label.set_text("Playing %s" % name)
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
        dialogs.AboutDialog()

    def reset(self, *args):
        """Reset the desktop to it's initial state."""
        if self.running_game:
            self.running_game.stop()
            self.stop_button.set_sensitive(False)

    # Callbacks
    def on_clear_search(self, widget, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            widget.set_text('')

    def on_connect(self, *args):
        """Callback when a user connects to his account."""
        login_dialog = dialogs.ClientLoginDialog()
        login_dialog.connect('connected', self.on_connect_success)

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
        system.xdg_open("http://lutris.net/user/register")

    def on_synchronize_manually(self, *args):
        """Callback when Synchronize Library is activated."""
        credentials = api.read_api_key()
        if credentials:  # Is connected
            self.sync_library()
        else:
            sync = Sync()
            async_call(
                sync.sync_steam_local,
                lambda r, e: async_call(self.sync_icons, None),
                caller=self
            )
        # Update Runtime
        async_call(runtime.update_runtime, None, self.set_status)

    def on_resize(self, widget, *args):
        self.window_size = widget.get_size()

    def on_destroy(self, *args):
        """Signal for window close."""
        view_type = 'grid' if 'GridView' in str(type(self.view)) else 'list'
        settings.write_setting('view_type', view_type)
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
        self.filter_installed = widget.get_active()
        setting_value = 'true' if self.filter_installed else 'false'
        settings.write_setting(
            'filter_installed', setting_value
        )
        self.switch_view(self.current_view_type)

    def on_pga_menuitem_activate(self, _widget, _data=None):
        dialogs.PgaSourceDialog()

    def on_search_entry_changed(self, widget):
        self.view.game_store.filter_text = widget.get_text()
        self.view.emit('filter-updated')

    def _get_current_game_slug(self):
        """Return the slug of the current selected game while taking care of the
        double clic bug.
        """
        # Wait two seconds to avoid running a game twice
        if time.time() - self.game_launch_time < 2:
            return
        self.game_launch_time = time.time()
        return self.view.selected_game

    def on_game_clicked(self, *args):
        """Launch a game, or install it if it is not"""
        game_slug = self._get_current_game_slug()
        if not game_slug:
            return
        self.running_game = Game(game_slug)
        if self.running_game.is_installed:
            self.stop_button.set_sensitive(True)
            self.running_game.play()
        else:
            InstallerDialog(game_slug, self)

    def on_install_clicked(self, *args):
        """Install a game"""
        game_slug = self._get_current_game_slug()
        if not game_slug:
            return
        InstallerDialog(game_slug, self)

    def on_keypress(self, widget, event):
        if event.keyval == Gdk.KEY_F9:
            self.toggle_sidebar()

    def game_selection_changed(self, _widget):
        # Emulate double click to workaround GTK bug #484640
        # https://bugzilla.gnome.org/show_bug.cgi?id=484640
        if type(self.view) is GameGridView:
            is_double_click = time.time() - self.game_selection_time < 0.4
            is_same_game = self.view.selected_game == self.last_selected_game
            if is_double_click and is_same_game:
                self.on_game_clicked()
            self.game_selection_time = time.time()
            self.last_selected_game = self.view.selected_game

        sensitive = True if self.view.selected_game else False
        self.play_button.set_sensitive(sensitive)
        self.delete_button.set_sensitive(sensitive)

    def on_game_installed(self, view, slug):
        view.set_installed(Game(slug))
        self.sidebar_treeview.update()

    def on_image_downloaded(self, game_slug):
        is_installed = Game(game_slug).is_installed
        self.view.update_image(game_slug, is_installed)

    def add_manually(self, *args):
        game = Game(self.view.selected_game)
        add_game_dialog = AddGameDialog(self, game)
        add_game_dialog.run()
        if add_game_dialog.saved:
            self.view.set_installed(game)
            self.sidebar_treeview.update()

    def on_view_game_log_activate(self, widget):
        if not self.running_game:
            dialogs.ErrorDialog('No game log available')
            return
        log_title = u"Log for {}".format(self.running_game)
        log_window = LogWindow(log_title, self.window)
        log_window.logtextview.set_text(self.running_game.game_log)

    def add_game(self, _widget, _data=None):
        """Add a new game."""
        add_game_dialog = AddGameDialog(self)
        add_game_dialog.run()
        if add_game_dialog.saved:
            self.add_game_to_view(add_game_dialog.slug)

    def add_game_to_view(self, slug):
        if not slug:
            raise ValueError("Missing game slug")
        game = Game(slug)

        def do_add_game():
            self.view.add_game(game)
            self.switch_splash_screen()
            self.sidebar_treeview.update()
        GLib.idle_add(do_add_game)

    def on_remove_game(self, _widget, _data=None):
        selected_game = self.view.selected_game
        UninstallGameDialog(slug=selected_game,
                            callback=self.remove_game_from_view)

    def remove_game_from_view(self, game_slug, from_library=False):
        def do_remove_game():
            self.view.remove_game(game_slug)
            self.switch_splash_screen()
            self.sidebar_treeview.update()

        if from_library:
            GLib.idle_add(do_remove_game)
        else:
            self.view.update_image(game_slug, is_installed=False)
            self.sidebar_treeview.update()

    def on_browse_files(self, widget):
        game = Game(self.view.selected_game)
        path = game.get_browse_dir()
        if path and os.path.exists(path):
            system.xdg_open(path)
        else:
            dialogs.NoticeDialog(
                "Can't open %s \nThe folder doesn't exist." % path
            )

    def edit_game_configuration(self, _button):
        """Edit game preferences."""
        def on_dialog_saved():
            game = Game(dialog.slug)
            self.view.remove_game(game_slug)
            self.view.add_game(game)
            self.view.set_selected_game(game_slug)
            self.sidebar_treeview.update()

        game = Game(self.view.selected_game)
        game_slug = game.slug
        if game.is_installed:
            dialog = EditGameConfigDialog(self, game, on_dialog_saved)

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
        if icon_type == self.view.icon_type or not menuitem.get_active():
            return
        if self.current_view_type == 'grid':
            settings.write_setting('icon_type_gridview', icon_type)
        elif self.current_view_type == 'list':
            settings.write_setting('icon_type_listview', icon_type)
        self.switch_view(self.current_view_type)

    def create_menu_shortcut(self, *args):
        """Add the selected game to the system's Games menu."""
        game_slug = slugify(self.view.selected_game)
        game_name = Game(game_slug).name
        shortcuts.create_launcher(game_slug, game_name, menu=True)

    def create_desktop_shortcut(self, *args):
        """Create a desktop launcher for the selected game."""
        game_slug = slugify(self.view.selected_game)
        game_name = Game(game_slug).name
        shortcuts.create_launcher(game_slug, game_name, desktop=True)

    def remove_menu_shortcut(self, *args):
        game_slug = slugify(self.view.selected_game)
        shortcuts.remove_launcher(game_slug, menu=True)

    def remove_desktop_shortcut(self, *args):
        game_slug = slugify(self.view.selected_game)
        shortcuts.remove_launcher(game_slug, desktop=True)

    def toggle_sidebar(self):
        if self.sidebar_viewport.is_visible():
            self.sidebar_viewport.hide()
        else:
            self.sidebar_viewport.show()

    def on_sidebar_changed(self, widget):
        self.view.game_store.filter_runner = widget.get_selected_runner()
        self.view.emit('filter-updated')
