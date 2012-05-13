""" Main window for the Lutris interface """
import os

# pylint: disable=E0611
from gi.repository import Gtk

from lutris.util import log
from lutris.settings import get_data_path

from lutris.game import LutrisGame, get_list

from lutris.gui.dialogs import AboutDialog
from lutris.gui.common import NoticeDialog
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.addgamedialog import AddGameDialog
from lutris.gui.systemconfigdialog import SystemConfigDialog
from lutris.config import LutrisConfig
from lutris.desktop_control import LutrisDesktopControl
from lutris.gui.editgameconfigdialog import EditGameConfigDialog
#from lutris.game import get_list
#from lutris.gui.widgets import GameTreeView


class LutrisWindow:
    """Handler class for main window signals"""
    def __init__(self):
        ui_filename = os.path.join(get_data_path(), 'ui', 'LutrisWindow.ui')
        if not os.path.exists(ui_filename):
            msg = 'File %s not found' % ui_filename
            log.logger.error(msg)
            raise IOError(msg)
        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_filename)
        self.builder.connect_signals(self)
        #game_list = get_list()
        #game_treeview = GameTreeView(game_list)
        #game_treeview.connect('row-activated', self.game_launch)
        #game_treeview.connect('cursor-changed', self.select_game)
        #game_treeview.connect('button-press-event', self.mouse_menu)
        #games_scrollwindow = builder.get_object('games_scrollwindow')
        #games_scrollwindow.add_with_viewport(game_treeview)

        self.window = self.builder.get_object("window")
        self.window.show_all()

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
                    self.status_label.set_text("Playing %s (pid: %r)"\
                                               % (name, pid))
        else:
            self.status_label.set_text("Welcome to Lutris")
        for index in range(4):
            if os.path.exists("/dev/input/js%d" % index):
                self.joystick_icons[index].show()
            else:
                self.joystick_icons[index].hide()
        return True

    def on_destroy(self, *args):
        """Signal for window close"""
        Gtk.main_quit(*args)

    def mouse_menu(self, widget, event):
        """Contextual menu"""
        if event.button == 3:
            (_, self.paths) = widget.get_selection().get_selected_rows()
            try:
                self.edited_game_index = self.paths[0][0]
            except IndexError:
                return
            if len(self.paths) > 0:
                self.menu.popup(None, None, None, event.button, event.time)

    def about(self, _widget, _data=None):
        """Opens the about dialog"""
        AboutDialog()

    def get_selected_game(self):
        """Return the currently selected game in the treeview"""
        game_selection = self.game_treeview.get_selection()
        model, select_iter = game_selection.get_selected()
        game_name = model.get_value(select_iter, 0)
        return game_name

    def select_game(self, treeview):
        """ Method triggered when a game is selected in the list. """
        #Set buttons states
        self.play_button.set_sensitive(True)
        self.reset_button.set_sensitive(True)
        self.delete_button.set_sensitive(True)
        self.game_cover.activate_drop()

        game_selected = treeview.get_selection()
        model, select_iter = game_selected.get_selected()
        if select_iter:
            self.game_name = model.get_value(select_iter, 0)
            self.game_cover.set_game_cover(self.game_name)

    def remove_game(self, _widget, _data=None):
        """Remove game configuration file

        Note: this won't delete the actual game
        """
        game_selection = self.game_treeview.get_selection()
        model, select_iter = game_selection.get_selected()
        game_name = model.get_value(select_iter, 0)
        self.lutris_config.remove(game_name)
        self.game_treeview.remove_row(select_iter)
        self.status_label.set_text("Removed game")

    def on_connect(self, widget):
        """Callback when a user connects to his account"""
        NoticeDialog("This functionnality is not yet implemented.")

    def on_runners_activate(self, _widget, _data=None):
        """Callback when manage runners is activated"""
        RunnersDialog()

    def on_preferences_activate(self, _widget, _data=None):
        """Callback when preferences is activated"""
        SystemConfigDialog()

    def import_scummvm(self, _widget, _data=None):
        """Callback for importing scummvm games"""
        from lutris.runners.scummvm import import_games
        new_games = import_games()
        for new_game in new_games:
            self.game_treeview.add_row(new_game)
        self.game_treeview.sort_rows()

    def import_steam(self, _widget, _data=None):
        """Callback for importing Steam games"""
        NoticeDialog("Import from steam not yet implemented")

    def on_play_clicked(self, _widget):
        """Callback for the play button"""
        self.game_launch()

    def game_launch(self, _treeview=None, _arg1=None, _arg2=None):
        """Launch a game"""
        self.running_game = LutrisGame(self.get_selected_game())
        self.running_game.play()

    def reset(self, _widget, _data=None):
        """Reset the desktop to it's initial state"""
        if hasattr(self, "running_game"):
            self.running_game.quit_game()
            self.status_label.set_text("Stopped %s"\
                                       % self.running_game.get_real_name())
        else:
            LutrisDesktopControl().reset_desktop()

    def add_game(self, _widget, _data=None):
        """ MAnually add a game """
        add_game_dialog = AddGameDialog(self)
        if hasattr(add_game_dialog, "game_info"):
            game_info = add_game_dialog.game_info
            self.game_treeview.add_row(game_info)
            self.game_treeview.sort_rows()

    def edit_game_name(self, _button):
        """Change game name"""
        self.game_cell.set_property('editable', True)
        self.game_treeview.set_cursor(self.paths[0][0], self.game_column, True)

    def game_name_edited_callback(self, _widget, index, new_name):
        """ Update the game's name """
        self.game_treeview.get_model()[index][0] = new_name
        new_name_game_config = LutrisConfig(game=self.get_selected_game())
        new_name_game_config.config["realname"] = new_name
        new_name_game_config.save(config_type="game")
        self.game_cell.set_property('editable', False)

    def edit_game_configuration(self, _button):
        """Edit game preferences"""

        game = self.get_selected_game()
        EditGameConfigDialog(self, game)
