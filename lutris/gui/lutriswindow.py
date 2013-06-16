""" Main window for the Lutris interface """
# pylint: disable=E0611
import os
import json

from gi.repository import Gtk, GLib, Gio, GObject

from lutris import api
from lutris import pga
from lutris import game
from lutris import settings
from lutris.config import LutrisConfig
from lutris.shortcuts import create_launcher
from lutris.util.strings import slugify
from lutris.util import resources
from lutris.gui import dialogs
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.addgamedialog import AddGameDialog
from lutris.gui.widgets import GameTreeView, GameIconView
from lutris.gui.systemconfigdialog import SystemConfigDialog
from lutris.gui.editgameconfigdialog import EditGameConfigDialog

GAME_VIEW = 'icon'


def switch_to_view(view=GAME_VIEW):
    game_list = pga.get_games()
    if view == 'icon':
        view = GameIconView(game_list)
    elif view == 'list':
        view = GameTreeView(game_list)
    view.show_all()
    return view


class LutrisWindow(object):
    """Handler class for main window signals"""
    def __init__(self):

        ui_filename = os.path.join(
            settings.get_data_path(), 'ui', 'LutrisWindow.ui'
        )
        if not os.path.exists(ui_filename):
            raise IOError('File %s not found' % ui_filename)

        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_filename)

        # load config
        window_config = self.load_view()
        width = window_config.get('width', 800)
        height = window_config.get('height', 600)
        self.window_size = (width, height)
        view_type = window_config.get('view_type', 'icon')

        self.view = switch_to_view(view_type)

        view_menuitem = self.builder.get_object("iconview_menuitem")
        view_menuitem.set_active(view_type == 'icon')
        view_menuitem = self.builder.get_object("listview_menuitem")
        view_menuitem.set_active(view_type == 'list')

        # Scroll window
        self.games_scrollwindow = self.builder.get_object('games_scrollwindow')
        self.games_scrollwindow.add(self.view)
        #Status bar
        self.status_label = self.builder.get_object('status_label')
        self.joystick_icons = []
        # Buttons
        self.reset_button = self.builder.get_object('reset_button')
        self.reset_button.set_sensitive(False)
        self.delete_button = self.builder.get_object('delete_button')
        self.delete_button.set_sensitive(False)
        self.play_button = self.builder.get_object('play_button')
        self.play_button.set_sensitive(False)

        #Contextual menu
        menu_actions = [
            ('Play', self.game_launch),
            ('Configure', self.edit_game_configuration),
            ('Create desktop shortcut', self.create_desktop_shortcut),
            ('Create global menu shortcut', self.create_menu_shortcut)
        ]
        self.menu = Gtk.Menu()
        for action in menu_actions:
            subitem = Gtk.ImageMenuItem(action[0])
            subitem.connect('activate', action[1])
            self.menu.append(subitem)
        self.menu.show_all()
        self.view.contextual_menu = self.menu

        #Timer
        self.timer_id = GLib.timeout_add(1000, self.refresh_status)
        self.window = self.builder.get_object("window")
        self.window.resize_to_geometry(width, height)
        self.window.show_all()

        self.builder.connect_signals(self)
        self.connect_signals()

        GObject.idle_add(self.sync_db, None)

    def sync_db(self, data=None):
        game_list = pga.get_games()
        Gio.io_scheduler_push_job(api.get_library, None,
                                  GLib.PRIORITY_DEFAULT_IDLE, None)
        resources.fetch_banners([game_info['slug'] for game_info in game_list])

    def connect_signals(self):
        """Connects signals from the view with the main window.
           This must be called each time the view is rebuilt.
        """
        self.view.connect("game-activated", self.game_launch)
        self.view.connect("game-selected", self.game_selection_changed)
        self.window.connect("configure-event", self.get_size)

    def get_size(self, widget, _):
        self.window_size = widget.get_size()

    def refresh_status(self):
        """Refresh status bar"""
        if hasattr(self, "running_game"):
            if hasattr(self.running_game.game_thread, "pid"):
                pid = self.running_game.game_thread.pid
                name = self.running_game.get_real_name()
                if pid == 99999:
                    self.status_label.set_text("Preparing to launch %s" % name)
                elif pid is None:
                    self.status_label.set_text("Game has quit")
                else:
                    self.status_label.set_text("Playing %s (pid: %r)"
                                               % (name, pid))
        else:
            self.status_label.set_text("")
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
        """Opens the about dialog"""
        dialogs.AboutDialog()

    def remove_game(self, _widget, _data=None):
        """Remove game configuration file
        Note: this won't delete the actual game
        """
        game = self.view.selected_game[0]
        config = LutrisConfig(game=game)
        config.remove()
        self.view.remove_game(game)

    # Callbacks
    def on_connect(self, *args):
        """Callback when a user connects to his account"""
        login_dialog = dialogs.ClientLoginDialog()
        login_dialog.connect('connected', self.on_connect_success)

    def on_connect_success(self, dialog, token):
        self.status_label.set_text("Connected")

    def on_destroy(self, *args):
        """Signal for window close"""
        self.save_view()
        Gtk.main_quit(*args)

    def on_runners_activate(self, _widget, _data=None):
        """Callback when manage runners is activated"""
        RunnersDialog()

    def on_preferences_activate(self, _widget, _data=None):
        """Callback when preferences is activated"""
        SystemConfigDialog()

    def on_pga_menuitem_activate(self, _widget, _data=None):
        dialogs.PgaSourceDialog()

    def import_scummvm(self, _widget, _data=None):
        """Callback for importing scummvm games"""
        from lutris.runners.scummvm import import_games
        new_games = import_games()
        if not new_games:
            dialogs.NoticeDialog("No ScummVM games found")
        else:
            for new_game in new_games:
                self.view.add_game(new_game)

    def on_search_entry_changed(self, widget):
        self.view.emit('filter-updated', widget.get_text())

    def game_launch(self, *args):
        """Launch a game"""
        if self.view.selected_game:
            self.running_game = game.LutrisGame(self.view.selected_game)
            self.running_game.play()

    def reset(self, *args):
        """Reset the desktop to it's initial state"""
        if self.running_game:
            self.running_game.quit_game()
            self.status_label.set_text("Stopped %s"
                                       % self.running_game.get_real_name())
            self.running_game = None

    def game_selection_changed(self, _widget):
        sensitive = True if self.view.selected_game else False
        self.play_button.set_sensitive(sensitive)
        self.delete_button.set_sensitive(sensitive)

    def add_game(self, _widget, _data=None):
        """ Manually add a game """
        add_game_dialog = AddGameDialog(self)
        if hasattr(add_game_dialog, "game_info"):
            game_info = add_game_dialog.game_info
            self.view.game_store.add_game(game_info)

    def edit_game_configuration(self, _button):
        """Edit game preferences"""
        EditGameConfigDialog(self, self.view.selected_game)

    def on_iconview_toggled(self, menuitem):
        """Switches between icon view and list view"""
        self.view.destroy()
        self.view = switch_to_view('icon' if menuitem.get_active() else 'list')
        self.view.contextual_menu = self.menu
        self.connect_signals()
        self.games_scrollwindow.add_with_viewport(self.view)

    def create_menu_shortcut(self, *args):
        """Adds the game to the system's Games menu"""
        game_slug = slugify(self.view.selected_game)
        create_launcher(game_slug, menu=True)
        dialogs.NoticeDialog(
            "Shortcut added to the Games category of the global menu.")

    def create_desktop_shortcut(self, *args):
        """Adds the game to the system's Games menu"""
        game_slug = slugify(self.view.selected_game)
        create_launcher(game_slug, desktop=True)
        dialogs.NoticeDialog('Shortcut created on your desktop.')

    def get_config_path(self):
        return os.path.join(settings.CONFIG_DIR, "lutris.config")

    def save_view(self):
        config_path = self.get_config_path()
        window_config = {}
        window_config['view_type'] = 'icon' \
            if 'IconView' in str(type(self.view)) else 'list'
        window_config['width'], window_config['height'] = self.window_size
        with open(config_path, 'w') as config_handler:
            config_handler.write(json.dumps(window_config))

    def load_view(self):
        config_path = self.get_config_path()
        if not os.path.exists(config_path):
            return {}
        with open(config_path, 'r') as config_file:
            config = json.loads(config_file.read())
        return config
