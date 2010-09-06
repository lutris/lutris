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

try:
    import LaunchpadIntegration
    LAUNCHPAD_AVAILABLE = True
except ImportError:
    LAUNCHPAD_AVAILABLE = False

import gtk
import os
import gobject
import logging

import lutris.runners
from lutris.game import LutrisGame
from lutris.config import LutrisConfig
from lutris.gui.common_dialogs import NoticeDialog
from lutris.gui.dictionary_grid import DictionaryGrid
from lutris.gui.ftpdialog import FtpDialog
from lutris.gui.runnersdialog import RunnersDialog
from lutris.gui.addgamedialog import AddGameDialog
from lutris.gui.mountisodialog import MountIsoDialog
from lutris.gui.installerdialog import InstallerDialog
from lutris.gui.systemconfigdialog import SystemConfigDialog
from lutris.gui.googleimagedialog import GoogleImageDialog
from lutris.gui.editgameconfigdialog import EditGameConfigDialog
from lutris.gui.aboutdialog import NewAboutLutrisDialog
from lutris.desktop_control import LutrisDesktopControl

import lutris.coverflow.coverflow

class LutrisWindow(gtk.Window):
    """ Main Lutris window """
    __gtype_name__ = "LutrisWindow"
    
    def __init__(self):
        super(LutrisWindow, self).__init__()
        self.data_path = None
        self.builder = None
        
        # Load Lutris configuration
        # TODO : this sould be useless soon (hint: remove() ) 
        self.lutris_config = LutrisConfig()
        
        
        # Widgets
        self.status_label = None
        self.menu = None
        self.game_cover_image = None
        self.toolbar = None
        
        self.joystick_icons = []

    def finish_initializing(self, builder, data_path):
        """ Method used by gtkBuilder to instanciate the window. """
        self.data_path = data_path
        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)

        self.set_title("Lutris")

        # https://wiki.ubuntu.com/UbuntuDevelopment/Internationalisation/Coding
        # for more information about LaunchpadIntegration
        global LAUNCHPAD_AVAILABLE
        if LAUNCHPAD_AVAILABLE: 
            helpmenu = self.builder.get_object('menu3')
            if helpmenu:
                LaunchpadIntegration.set_sourcepackagename('lutris')
                LaunchpadIntegration.add_items(helpmenu, 0, False, True)
            else:
                LAUNCHPAD_AVAILABLE = False

        # TODO: The game_cover_image will be moved inot it's own widget
        self.game_cover_image = self.builder.get_object("game_cover_image")
        self.game_cover_image.set_from_file(
            os.path.join(data_path, "media/background.png")
        )
        
        #Context menu
        game_rename = "Rename", self.edit_game_name
        game_config = "Configure", self.edit_game_configuration
        game_get_cover = "Get cover", self.get_cover
        menu_actions = [game_rename, game_config, game_get_cover]
        self.menu = gtk.Menu()
        for item in menu_actions:
            if item == None:
                subitem = gtk.SeparatorMenuItem()
            else:
                subitem = gtk.ImageMenuItem(item[0])
                subitem.connect("activate", item[1])
                self.menu.append(subitem)
        self.menu.show_all()

        #Status bar
        self.status_label = self.builder.get_object("status_label")
        self.status_label.set_text("Ready to roll !")

        self.joystick_icons.append(self.builder.get_object("js0image"))
        self.joystick_icons.append(self.builder.get_object("js1image"))
        self.joystick_icons.append(self.builder.get_object("js2image"))
        self.joystick_icons.append(self.builder.get_object("js3image"))
        for joystick_icon in self.joystick_icons:
            joystick_icon.hide()

        # Toolbar
        self.toolbar = self.builder.get_object("lutris_toolbar")

        # Game list
        self.game_list = self.get_game_list()
        self.game_list_grid_view = DictionaryGrid(self.game_list,
                                                  ["Game Name", "Runner"])
        self.game_list_grid_view.connect('row-activated', self.game_launch)
        self.game_list_grid_view.connect("cursor-changed", self.select_game)
        self.game_list_grid_view.connect("button-press-event", self.mouse_menu)
        self.game_list_grid_view.show()

        self.game_column = self.game_list_grid_view.get_column(0)

        self.game_cell = self.game_column.get_cell_renderers()[0]
        self.game_cell.connect('edited', self.game_name_edited_callback)

        self.game_list_scrolledwindow = self.builder.get_object("game_list_scrolledwindow")
        self.game_list_scrolledwindow.add_with_viewport(self.game_list_grid_view)

        #Timer
        self.timer_id = gobject.timeout_add(1000, self.refresh_status)

    def refresh_status(self):
        # FIXME !!
        # if hasattr(self.running_game.game_process, "pid"):
        #     self.status_text = "Game is running (pid: %s)" % str(self.running_game.game_process.pid)
        #     self.status_bar.push(self.status_bar_context_id,self.status_text)
        # else:
        #     self.status_bar.push(self.status_bar_context_id,"Welcome to Lutris")
        for index in range(0, 3):
            if os.path.exists("/dev/input/js%d" % index):
                self.joystick_icons[index].show()
            else:
                self.joystick_icons[index].hide()
        return True

    def get_game_list(self):
        game_list = []
        for file in os.listdir(lutris.constants.game_config_path):
            if file.endswith(lutris.constants.config_extension):
                game_name = file[:len(file) - len(lutris.constants.config_extension)]
                Game = LutrisGame(game_name)
                if not Game.load_success:
                    message = "Error while loading configuration for %s" % game_name
                    error_dialog = gtk.MessageDialog(parent=self, flags=0,
                                                     type=gtk.MESSAGE_ERROR,
                                                     buttons=gtk.BUTTONS_OK,
                                                     message_format=message)
                    error_dialog.run()
                    error_dialog.destroy()
                game_list.append({"Game Name":Game.real_name, "Runner":Game.runner_name, "name":game_name})
        return game_list

    def about(self, widget, data=None):
        """about - display the about box for lutris """
        about = NewAboutLutrisDialog(self.data_path)
        about.run()
        about.destroy()

    def quit(self, widget, data=None):
        """quit - signal handler for closing the LutrisWindow"""

        self.destroy()

    def on_destroy(self, widget, data=None):
        """on_destroy - called when the LutrisWindow is close. """
        #clean up code for saving application state should be added here
        gtk.main_quit()

    def mouse_menu(self, widget, event):
        if event.button == 3:
            (model, self.paths) = widget.get_selection().get_selected_rows()
            try:
                self.edited_game_index = self.paths[0][0]
            except IndexError:
                return
            if len(self.paths) > 0:
                self.menu.popup(None, None, None, event.button, event.time)

    def remove_game(self, widget, data=None):
        """Remove game configuration file

        Note: this won't delete the actual game
        
        """
        if not self.gameName:
            return
        self.lutris_config.remove(self.gameName)
        self.game_list_grid_view.remove_selected_rows()
        self.status_label.set_text("Removed game")

    def game_launch(self, treeview, arg1, arg2):
        self.running_game = LutrisGame(self.get_selected_game())
        self.running_game.play()

    def get_selected_game(self):
        gameSelection = self.game_list_grid_view.get_selection()
        model, select_iter = gameSelection.get_selected()
        game_name = model.get_value(select_iter, 2)
        return game_name["name"]

    def select_game(self, treeview):
        gameSelection = treeview.get_selection()
        model, select_iter = gameSelection.get_selected()
        if select_iter:
            self.gameName = model.get_value(select_iter, 2)["name"]
            self.set_game_cover()

    def on_fullscreen_clicked(self, widget):
        """ Switch to coverflow mode """
        coverflow = lutris.coverflow.coverflow.coverflow()
        if coverflow:
            if coverflow == "NOCOVERS":
                message = "You need covers for your games to switch to fullscreen mode." 
                 
                NoticeDialog(message)
                return
            if coverflow == "NOPYGLET":
                NoticeDialog("python-pyglet is not installed")
                return
            filename = os.path.basename(coverflow)
            game_name = filename[:filename.rfind(".")]
            running_game = LutrisGame(game_name)
            running_game.play()

    def reset(self, widget, data=None):
        if hasattr(self, "running_game"):
            self.running_game.quit_game()
        else:
            LutrisDesktopControl().reset_desktop()

    def install_game(self, widget, data=None):
        installer_dialog = InstallerDialog(self)

    def add_game(self, widget, data=None):
        add_game_dialog = AddGameDialog(self)
        if hasattr(add_game_dialog, "game_info"):
            game_info = add_game_dialog.game_info
            self.game_list_grid_view.append_row(game_info)

    def import_cedega(self, widget, data=None):
        from lutris.runners.cedega import cedega
        cedega = cedega()
        result = cedega.import_games()
        if result is not True:
            NoticeDialog(result)
        self.get_game_list()

    def import_steam(self, widget, data=None):
        NoticeDialog("Import from steam not yet implemented")

    def import_scummvm(self, widget, data=None):
        scummvm = lutris.runners.scummvm.scummvm()
        scummvm.import_games()
        games = self.get_game_list()
        current_game_names = []
        for row in self.game_list_grid_view.rows:
            current_game_names.append(row["name"])
        for game in games:
            if game['name'] not in current_game_names:
                self.game_list_grid_view.append_row(game)

    def on_getfromftp_clicked(self, widget, data=None):
        FtpDialog()

    def system_preferences(self, widget, data=None):
        SystemConfigDialog()

    def runner_preferences(self, widget, data=None):
        RunnersDialog()

    def on_mount_iso_menuitem_activate(self, widget):
        MountIsoDialog()

    def edit_game_name(self, button):
        """Change game name"""
        self.game_cell.set_property('editable', True)
        self.game_list_grid_view.set_cursor(self.paths[0][0], self.game_column, True)

    def game_name_edited_callback(self, widget, index, new_name):
        self.game_list_grid_view.get_model()[index][0] = new_name
        new_name_game_config = LutrisConfig(game=self.get_selected_game())
        new_name_game_config.config["realname"] = new_name
        new_name_game_config.save(type="game")
        self.game_cell.set_property('editable', False)

    def edit_game_configuration(self, button):
        """Edit game preferences"""
        game = self.get_selected_game()
        EditGameConfigDialog(self, game)

    def get_cover(self, button):
        """Fetch cover from Google Image"""
        game = self.get_selected_game()
        GoogleImageDialog(game)

    def set_game_cover(self):
        if self.gameName:
            extensions = ["png", "jpg", "jpeg"]
            for extension in extensions:
                coverFile = os.path.join(lutris.constants.cover_path,
                                         self.gameName + "." + extension)
                if os.path.exists(coverFile):
                    #Resize the image
                    cover_pixbuf = gtk.gdk.pixbuf_new_from_file(coverFile)
                    dest_w = 250.0
                    h = cover_pixbuf.get_height()
                    w = cover_pixbuf.get_width()
                    dest_h = h * (dest_w / w)
                    self.game_cover_image.set_from_pixbuf(cover_pixbuf.scale_simple(int(dest_w), int(dest_h), gtk.gdk.INTERP_BILINEAR))
                    return
                else:
                    self.game_cover_image.set_from_file("data/media/background.png")
