"""Main window for the Lutris interface."""
# pylint: disable=E0611
import os
import subprocess
import time

from gi.repository import Gio, Gtk, Gdk, GLib

from lutris import api, pga, settings
from lutris.game import Game, get_game_list
from lutris.shortcuts import create_launcher
from lutris.sync import Sync

from lutris.util import runtime
from lutris.util import resources
from lutris.util.log import logger
from lutris.util.jobs import async_call
from lutris.util.strings import slugify
from lutris.util import datapath

from lutris.gui import dialogs
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
    def __init__(self, application):

        ui_filename = os.path.join(
            datapath.get(), 'ui', 'LutrisWindow.ui'
        )
        if not os.path.exists(ui_filename):
            raise IOError('File %s not found' % ui_filename)

        self.application = application

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
        logger.debug("Getting game list")
        game_list = get_game_list(self.filter_installed)
        logger.debug("Switching view")
        self.view = load_view(view_type, game_list,
                              icon_type=self.icon_type)
        logger.debug("Connecting signals")
        self.main_box = self.builder.get_object('main_box')
        self.splash_box = self.builder.get_object('splash_box')
        self.stack = self.builder.get_object('stack')

        # Scroll window
        self.games_scrollwindow = self.builder.get_object('games_scrollwindow')
        self.games_scrollwindow.add(self.view)
        # Status bar
        self.status_label = self.builder.get_object('status_label')
        # Search
        self.search_entry = self.builder.get_object('search_entry')
        self.search_revealer = self.builder.get_object('search_revealer')

        # Contextual menu
        menu_callbacks = [
            ('play', self.on_game_clicked),
            ('install', self.on_install_clicked),
            ('add', self.add_manually),
            ('configure', self.edit_game_configuration),
            ('browse', self.on_browse_files),
            ('desktop-shortcut', self.create_desktop_shortcut),
            ('menu-shortcut', self.create_menu_shortcut),
            ('remove', self.on_remove_game),
        ]
        self.menu = ContextualMenu(menu_callbacks)
        self.view.contextual_menu = self.menu

        # Timer
        self.timer_id = GLib.timeout_add(2000, self.refresh_status)

        # Window initialization
        self.window = self.builder.get_object("window")
        self.window.set_application(application)
        self.window.resize_to_geometry(width, height)
        self.window.show_all()
        self.builder.connect_signals(self)
        self.connect_signals()

        # Popovers
        builder = Gtk.Builder.new_from_file(os.path.join(datapath.get(), 'ui', 'account-menu-popover.ui'))
        builder.connect_signals(self)
        popover = builder.get_object('account_menu_widget')
        account_btn = self.builder.get_object('account_menu_btn')
        account_btn.set_popover(popover)
        self.connection_label = builder.get_object('connection_label')
        self.disconnect_btn = builder.get_object('disconnect_btn')
        self.sync_btn = builder.get_object('sync_btn')
        self.register_btn = builder.get_object('register_btn')
        self.connect_btn = builder.get_object('connect_btn')

        builder = Gtk.Builder.new_from_file(os.path.join(datapath.get(), 'ui', 'view-menu-popover.ui'))
        popover = builder.get_object('view_menu_widget')
        view_menu_btn = self.builder.get_object('view_menu_btn')
        view_menu_btn.set_popover(popover)
        filter_box = builder.get_object('filter_box')
        runners = ['all',] + pga.get_runners()
        for runner in runners: # FIXME: Support refreshing
            button = Gtk.ModelButton.new()
            button.props.text = runner
            button.props.action_name = 'win.filter-runner'
            button.props.action_target = GLib.Variant.new_string(runner)
            filter_box.add(button)
        filter_box.show_all()

        self.zoom_level = builder.get_object('zoom_level_scale')
        self.zoom_level.connect('value-changed', self.on_zoom_changed)

        # Actions
        action = Gio.SimpleAction.new_stateful('search', None, GLib.Variant.new_boolean(False))
        action.connect('change-state', self.on_search_action)
        self.window.add_action(action)
        application.add_accelerator('<Primary>f', 'win.search', None)

        action = Gio.SimpleAction.new_stateful('show-installed-only', None,
                                               GLib.Variant.new_boolean(self.filter_installed))
        action.connect('change-state', self.on_show_installed_only_changed)
        self.window.add_action(action)

        variant = GLib.Variant.new_string(view_type)
        action = Gio.SimpleAction.new_stateful('view-mode', variant.get_type(), variant)
        action.connect('change-state', self.on_view_mode_changed)
        self.window.add_action(action)

        variant = GLib.Variant.new_string('all')
        action = Gio.SimpleAction.new_stateful('filter-runner', variant.get_type(), variant)
        action.connect('change-state', self.on_runner_filter_changed)
        self.window.add_action(action)

        self.stop_action = Gio.SimpleAction.new('stop-current-game', None)
        self.stop_action.connect('activate', self.on_stop_game_action)
        self.stop_action.set_enabled(False)
        self.window.add_action(self.stop_action)

        action = Gio.SimpleAction.new('view-last-logs', None)
        action.connect('activate', self.on_view_game_log_activate)
        self.window.add_action(action)

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
            self.stack.set_visible_child(self.splash_box)
        else:
            self.stack.set_visible_child(self.main_box)

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

        scale = {'icon':0, 'banner_small':1, 'banner':2}
        self.zoom_level.set_value(scale[self.icon_type])

    def sync_library(self):
        def set_library_synced(result, error):
            self.set_status("Library synced")
            self.switch_splash_screen()
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
                self.stop_action.set_enabled(False)
            elif self.running_game.state == self.running_game.STATE_RUNNING:
                self.status_label.set_text("Playing %s" % name)
        return True

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
        self.disconnect_btn.set_visible(is_connected)
        self.sync_btn.set_visible(is_connected)
        self.connect_btn.set_visible(not is_connected)
        self.register_btn.set_visible(not is_connected)
        connection_status = "Connected as %s" % username if is_connected else "Not connected"
        logger.info(connection_status)
        self.connection_label.set_text(connection_status)

    def on_register_account(self, *args):
        Gtk.show_uri(None, "http://lutris.net/user/register", Gdk.CURRENT_TIME)

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
        self.application.quit()
        logger.debug("Quitting lutris")

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
            self.stop_action.set_enabled(True)
            self.running_game.play()
        else:
            InstallerDialog(game_slug, self)

    def on_install_clicked(self, *args):
        """Install a game"""
        game_slug = self._get_current_game_slug()
        if not game_slug:
            return
        InstallerDialog(game_slug, self)

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

    def on_game_installed(self, view, slug):
        view.set_installed(Game(slug))

    def on_image_downloaded(self, game_slug):
        is_installed = Game(game_slug).is_installed
        self.view.update_image(game_slug, is_installed)

    def add_manually(self, *args):
        game = Game(self.view.selected_game)
        add_game_dialog = AddGameDialog(self, game)
        add_game_dialog.run()
        if add_game_dialog.saved:
            self.view.set_installed(game)

    def on_view_game_log_activate(self, action, param):
        if not self.running_game:
            dialogs.ErrorDialog('No game log available')
            return
        log_title = "Log for {}".format(self.running_game)
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
        GLib.idle_add(do_add_game)

    def on_remove_game(self, _widget, _data=None):
        selected_game = self.view.selected_game
        UninstallGameDialog(slug=selected_game,
                            callback=self.remove_game_from_view)

    def remove_game_from_view(self, game_slug, from_library=False):
        def do_remove_game():
            self.view.remove_game(game_slug)
            self.switch_splash_screen()

        if from_library:
            GLib.idle_add(do_remove_game)
        else:
            self.view.update_image(game_slug, is_installed=False)

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
        game = Game(self.view.selected_game)
        game_slug = game.slug
        if game.is_installed:
            dialog = EditGameConfigDialog(self, game)
            if dialog.saved:
                game = Game(dialog.slug)
                self.view.remove_game(game_slug)
                self.view.add_game(game)
                self.view.set_selected_game(game_slug)

    def create_menu_shortcut(self, *args):
        """Add the game to the system's Games menu."""
        game_slug = slugify(self.view.selected_game)
        create_launcher(game_slug, menu=True)
        dialogs.NoticeDialog(
            "Shortcut added to the Games category of the global menu.")

    def create_desktop_shortcut(self, *args):
        """Add the game to the system's Games menu."""
        game_slug = slugify(self.view.selected_game)
        create_launcher(game_slug, desktop=True)
        dialogs.NoticeDialog('Shortcut created on your desktop.')

    def on_stop_game_action(self, action, param):
        if self.running_game:
            self.running_game.stop()
            self.stop_action.set_enabled(False)

    def on_search_action(self, action, value):
        action.set_state(value)
        if value.get_boolean():
            self.search_revealer.set_reveal_child(True)
            self.search_entry.grab_focus()
        else:
            self.search_revealer.set_reveal_child(False)
            self.view.grab_focus()

    def on_view_mode_changed(self, action, value):
        action.set_state(value)
        view_type = value.get_string()
        self.switch_view(view_type)

    def on_show_installed_only_changed(self, action, value):
        action.set_state(value)
        self.filter_installed = value.get_boolean()
        setting_value = 'true' if self.filter_installed else 'false'
        settings.write_setting(
            'filter_installed', setting_value
        )
        self.switch_view(self.current_view_type)

    def on_runner_filter_changed(self, action, value):
        action.set_state(value)

        runner = value.get_string()
        if runner == 'all':
            runner = None
        if self.view.game_store.filter_runner != runner:
            self.view.game_store.filter_runner = runner
            self.view.emit('filter-updated')

    def on_zoom_changed(self, _range):
        scale = ('icon', 'banner_small', 'banner')
        icon_type = scale[int(_range.get_value())]
        if icon_type == self.icon_type:
            return

        if self.current_view_type == 'grid':
            settings.write_setting('icon_type_gridview', icon_type)
        elif self.current_view_type == 'list':
            settings.write_setting('icon_type_listview', icon_type)
        self.switch_view(self.current_view_type)
