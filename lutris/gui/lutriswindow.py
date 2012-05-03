# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

"""Main window module"""

try:
    #pylint: disable=F0401
    import LaunchpadIntegration
    LAUNCHPAD_AVAILABLE = True
except ImportError:
    LAUNCHPAD_AVAILABLE = False

import gtk
import os
import gobject

from lutris.gui.widgets import GameTreeView, GameCover
from lutris.game import LutrisGame, get_list
from lutris.config import LutrisConfig
from lutris.gui.common import NoticeDialog
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.addgamedialog import AddGameDialog
from lutris.gui.systemconfigdialog import SystemConfigDialog
from lutris.gui.editgameconfigdialog import EditGameConfigDialog
from lutris.gui.aboutdialog import NewAboutLutrisDialog
from lutris.desktop_control import LutrisDesktopControl


class LutrisWindow(gtk.Window):
    """ Main Lutris window """
    __gtype_name__ = "LutrisWindow"

    def __init__(self):
        super(LutrisWindow, self).__init__()
        self.data_path = data_path
        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)
        self.set_title("Lutris")
        # https://wiki.ubuntu.com/UbuntuDevelopment/Internationalisation/Coding
        # for more information about LaunchpadIntegration
        if LAUNCHPAD_AVAILABLE:
            helpmenu = self.builder.get_object('help_menu')
            if helpmenu:
                LaunchpadIntegration.set_sourcepackagename('lutris')
                LaunchpadIntegration.add_items(helpmenu, 0, False, True)
        # Load Lutris configuration
        # TODO : this sould be useless soon (hint: remove())
        self.lutris_config = LutrisConfig()
        # Widgets
        self.status_label = None
        self.menu = None
        # Toolbar
        self.toolbar = self.builder.get_object('lutris_toolbar')

        self.game_cover = GameCover(parent=self)
        self.game_cover.desactivate_drop()
        cover_alignment = self.builder.get_object('cover_alignment')
        cover_alignment.add(self.game_cover)

        self.reset_button = self.builder.get_object('reset_button')
        self.reset_button.set_sensitive(False)
        self.delete_button = self.builder.get_object('delete_button')
        self.delete_button.set_sensitive(False)
        self.joystick_icons = []

    def finish_initializing(self, builder, data_path):
        """ Method used by gtkBuilder to instanciate the window. """
        #Contextual menu
        play = 'Play', self.game_launch
        rename = 'Rename', self.edit_game_name
        config = 'Configure', self.edit_game_configuration
        self.menu = gtk.Menu()
        for item in [play, rename, config]:
            if item == None:
                subitem = gtk.SeparatorMenuItem()
            else:
                subitem = gtk.ImageMenuItem(item[0])
                subitem.connect('activate', item[1])
                self.menu.append(subitem)

        #Status bar
        self.status_label = self.builder.get_object('status_label')
        self.status_label.set_text('Insert coin')

        for index in range(4):
            self.joystick_icons.append(
                self.builder.get_object('js' + str(index) + 'image')
            )
            self.joystick_icons[index].hide()


        # Game list
        self.game_list = get_list()
        self.game_treeview = GameTreeView(self.game_list)
        self.game_treeview.connect('row-activated', self.game_launch)
        self.game_treeview.connect('cursor-changed', self.select_game)
        self.game_treeview.connect('button-press-event', self.mouse_menu)

        self.game_column = self.game_treeview.get_column(1)
        self.game_cell = self.game_column.get_cell_renderers()[0]
        self.game_cell.connect('edited', self.game_name_edited_callback)

        self.games_scrollwindow = self.builder.get_object('games_scrollwindow')
        self.games_scrollwindow.add_with_viewport(self.game_treeview)

        # Set buttons state
        self.play_button = self.builder.get_object('play_button')
        self.play_button.set_sensitive(False)

        #Timer
        self.timer_id = gobject.timeout_add(1000, self.refresh_status)

        self.show_all()

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

    def quit(self, _widget, _data=None):
        """quit - signal handler for closing the LutrisWindow"""
        self.destroy()

    def on_destroy(self, _widget, _data=None):
        """on_destroy - called when the LutrisWindow is close. """
        gtk.main_quit()

    # Menu action handlers
    # - Lutris Menu
    def on_connect(self, _widget, _data=None):
        """Callback when a user connects to his account"""
        #ConnectDialog()
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

    # - Help menu
    def about(self, _widget, _data=None):
        """Opens the about dialog"""
        about = NewAboutLutrisDialog(self.data_path)
        about.run()
        about.destroy()

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

    def game_launch(self, _treeview=None, _arg1=None, _arg2=None):
        """Launch a game"""
        self.running_game = LutrisGame(self.get_selected_game())
        self.running_game.play()

    def on_play_clicked(self, _widget):
        """Callback for the play button"""
        self.game_launch()

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
