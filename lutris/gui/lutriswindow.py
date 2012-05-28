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

from gi.repository import Gtk
import os
from gi.repository import GObject

from lutris.gui.widgets import GameTreeView, GameCover
from lutris.gui.aboutdialog import NewAboutLutrisDialog


class LutrisWindow(Gtk.Window):
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
        self.menu = Gtk.Menu()
        for item in [play, rename, config]:
            if item == None:
                subitem = Gtk.SeparatorMenuItem()
            else:
                subitem = Gtk.ImageMenuItem(item[0])
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

        self.game_column = self.game_treeview.get_column(1)
        self.game_cell = self.game_column.get_cell_renderers()[0]
        self.game_cell.connect('edited', self.game_name_edited_callback)


        # Set buttons state
        self.play_button = self.builder.get_object('play_button')
        self.play_button.set_sensitive(False)

        #Timer
        self.timer_id = GObject.timeout_add(1000, self.refresh_status)

        self.show_all()



