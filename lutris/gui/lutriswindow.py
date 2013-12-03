""" Main window for the Lutris interface """
# pylint: disable=E0611
import os

from gi.repository import Gtk, GLib

from lutris import api
from lutris import pga
from lutris import settings
from lutris.game import Game, get_game_list
from lutris.shortcuts import create_launcher
from lutris.installer import InstallerDialog

from lutris.util import resources
from lutris.util.log import logger
from lutris.util.jobs import async_call
from lutris.util.strings import slugify

from lutris.gui import dialogs
from lutris.gui.uninstallgamedialog import UninstallGameDialog
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.addgamedialog import AddGameDialog
from lutris.gui.widgets import GameTreeView, GameIconView
from lutris.gui.systemconfigdialog import SystemConfigDialog
from lutris.gui.editgameconfigdialog import EditGameConfigDialog

GAME_VIEW = 'icon'


def switch_to_view(view=GAME_VIEW, games=[]):
    if view == 'icon':
        view = GameIconView(games)
    elif view == 'list':
        view = GameTreeView(games)
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
        width = int(settings.read_setting('width') or 800)
        height = int(settings.read_setting('height') or 600)
        self.window_size = (width, height)
        view_type = settings.read_setting('view_type') or 'icon'

        self.view = switch_to_view(view_type, get_game_list())

        self.icon_view_menuitem = self.builder.get_object("iconview_menuitem")
        self.icon_view_menuitem.set_active(view_type == 'icon')
        self.list_view_menuitem = self.builder.get_object("listview_menuitem")
        self.list_view_menuitem.set_active(view_type == 'list')
        self.icon_view_btn = self.builder.get_object('switch_grid_view_btn')
        self.icon_view_btn.set_active(view_type == 'icon')
        self.list_view_btn = self.builder.get_object('switch_list_view_btn')
        self.list_view_btn.set_active(view_type == 'list')

        # Scroll window
        self.games_scrollwindow = self.builder.get_object('games_scrollwindow')
        self.games_scrollwindow.add(self.view)
        #Status bar
        self.status_label = self.builder.get_object('status_label')
        self.joystick_icons = []
        # Buttons
        self.stop_button = self.builder.get_object('stop_button')
        self.stop_button.set_sensitive(False)
        self.delete_button = self.builder.get_object('delete_button')
        self.delete_button.set_sensitive(False)
        self.play_button = self.builder.get_object('play_button')
        self.play_button.set_sensitive(False)

        #Contextual menu
        menu_actions = [
            ('Play', self.on_game_clicked),
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
        self.timer_id = GLib.timeout_add(2000, self.refresh_status)
        self.window = self.builder.get_object("window")
        self.window.resize_to_geometry(width, height)
        self.window.show_all()

        self.builder.connect_signals(self)
        self.connect_signals()
        async_call(self.sync_db, None)

    def sync_db(self, *args):
        api.sync()
        game_list = pga.get_games()
        resources.fetch_banners([game_info['slug'] for game_info in game_list],
                                callback=self.on_image_downloaded)

    def connect_signals(self):
        """Connects signals from the view with the main window.
           This must be called each time the view is rebuilt.
        """
        self.view.connect("game-activated", self.on_game_clicked)
        self.view.connect("game-selected", self.game_selection_changed)
        self.window.connect("configure-event", self.get_size)

    def get_size(self, widget, _):
        self.window_size = widget.get_size()

    def refresh_status(self):
        """Refresh status bar"""
        if hasattr(self, "running_game"):
            if hasattr(self.running_game.game_thread, "pid"):
                pid = self.running_game.game_thread.pid
                name = self.running_game.name
                if pid == 99999:
                    self.status_label.set_text("Preparing to launch %s" % name)
                elif pid is None:
                    self.status_label.set_text("Game has quit")
                else:
                    self.status_label.set_text("Playing %s (pid: %r)"
                                               % (name, pid))
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
        selected_game = self.view.selected_game[0]
        UninstallGameDialog(game=selected_game, callback=self.on_game_deleted)

    def on_game_deleted(self, game_slug):
        self.view.remove_game(game_slug)

    # Callbacks
    def on_connect(self, *args):
        """Callback when a user connects to his account"""
        login_dialog = dialogs.ClientLoginDialog()
        login_dialog.connect('connected', self.on_connect_success)

    def on_connect_success(self, dialog, token):
        logger.info("Successfully connected to Lutris.net")
        self.status_label.set_text("Connected")
        async_call(self.sync_db, None)

    def on_destroy(self, *args):
        """Signal for window close"""
        view_type = 'icon' if 'IconView' in str(type(self.view)) else 'list'
        settings.write_setting('view_type', view_type)
        width, height = self.window_size
        settings.write_setting('width', width)
        settings.write_setting('height', height)
        Gtk.main_quit(*args)
        logger.debug("Quitting lutris")

    def on_runners_activate(self, _widget, _data=None):
        """Callback when manage runners is activated"""
        RunnersDialog()

    def on_preferences_activate(self, _widget, _data=None):
        """Callback when preferences is activated"""
        SystemConfigDialog()

    def on_pga_menuitem_activate(self, _widget, _data=None):
        dialogs.PgaSourceDialog()

    def on_image_downloaded(self, game_slug):
        self.view.update_image(game_slug)

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

    def on_game_clicked(self, *args):
        """Launch a game"""
        game_slug = self.view.selected_game[0]
        if game_slug:
            self.running_game = Game(game_slug)
            if self.running_game.is_installed:
                self.running_game.play()
            else:
                InstallerDialog(game_slug, self)

    def reset(self, *args):
        """Reset the desktop to it's initial state"""
        if self.running_game:
            self.running_game.quit_game()
            self.status_label.set_text("Stopped %s" % self.running_game.name)
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
            game = Game(game_info['slug'])
            self.view.game_store.add_game(game)

    def edit_game_configuration(self, _button):
        """Edit game preferences"""
        EditGameConfigDialog(self, self.view.selected_game)

    def on_viewmenu_toggled(self, menuitem):
        view_type = 'icon' if menuitem.get_active() else 'list'
        current_view = 'icon' if self.view.__class__.__name__ == "GameIconView" \
            else 'list'
        if view_type == current_view:
            return
        self.do_view_switch(view_type)
        self.icon_view_btn.set_active(view_type == 'icon')
        self.list_view_btn.set_active(view_type == 'list')

    def on_viewbtn_toggled(self, widget):
        view_type = 'icon' if widget.get_active() else 'list'
        current_view = 'icon' if self.view.__class__.__name__ == "GameIconView" \
            else 'list'
        if view_type == current_view:
            return
        self.list_view_menuitem.toggled()
        self.do_view_switch(view_type)

    def do_view_switch(self, view_type):
        """Switches between icon view and list view"""
        self.view.destroy()
        self.view = switch_to_view(view_type, get_game_list())
        self.view.contextual_menu = self.menu
        self.connect_signals()
        self.games_scrollwindow.add_with_viewport(self.view)
        self.view.show_all()
        self.view.check_resize()

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
