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

"""Game edition dialog"""

from gi.repository import Gtk

from lutris.config import LutrisConfig
from lutris.util.log import logger
from lutris.gui.gameconfigvbox import GameConfigVBox
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


# pylint: disable=R0904
class EditGameConfigDialog(Gtk.Dialog):
    """Game config edit dialog"""
    def __init__(self, parent, game):
        super(EditGameConfigDialog, self).__init__()
        self.parent_window = parent
        self.game = game
        self.set_title("Edit game configuration")
        self.set_size_request(500, 500)

        #Top label
        self.lutris_config = LutrisConfig(game=game)
        logger.debug(self.lutris_config.config)

        self.lutris_config.runner = self.lutris_config.runner

        game_name_label = Gtk.Label(label="Edit configuration for %s "
                                    % self.lutris_config.config["realname"])
        self.vbox.pack_start(game_name_label, False, False, 10)

        #Notebook
        config_notebook = Gtk.Notebook()
        self.vbox.pack_start(config_notebook, True, True, 0)

        #Game configuration tab
        self.game_config_vbox = GameConfigVBox(self.lutris_config, "game")
        game_config_scrolled_window = Gtk.ScrolledWindow()
        game_config_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                               Gtk.PolicyType.AUTOMATIC)
        game_config_scrolled_window.add_with_viewport(self.game_config_vbox)
        config_notebook.append_page(game_config_scrolled_window,
                                    Gtk.Label(label="Game Configuration"))

        #Runner configuration tab
        self.runner_config_box = RunnerConfigVBox(self.lutris_config, "game")
        runner_config_scrolled_window = Gtk.ScrolledWindow()
        runner_config_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                                 Gtk.PolicyType.AUTOMATIC)
        runner_config_scrolled_window.add_with_viewport(self.runner_config_box)
        config_notebook.append_page(runner_config_scrolled_window,
                                    Gtk.Label(label="Runner Configuration"))

        #System configuration tab
        self.system_config_box = SystemConfigVBox(self.lutris_config, "game")
        system_config_scrolled_window = Gtk.ScrolledWindow()
        system_config_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                                 Gtk.PolicyType.AUTOMATIC)
        system_config_scrolled_window.add_with_viewport(self.system_config_box)
        config_notebook.append_page(system_config_scrolled_window,
                                    Gtk.Label(label="Runner Configuration"))

        #Action Area
        cancel_button = Gtk.Button(None, Gtk.STOCK_CANCEL)
        add_button = Gtk.Button(None, Gtk.STOCK_EDIT)
        self.action_area.pack_start(cancel_button, True, True, 0)
        self.action_area.pack_start(add_button, True, True, 0)
        cancel_button.connect("clicked", self.close)
        add_button.connect("clicked", self.edit_game)

        self.show_all()
        self.run()

    def edit_game(self, _widget=None):
        """Save the changes"""
        logger.debug(self.lutris_config.config)
        self.lutris_config.save(config_type="game")
        self.destroy()

    def close(self, _widget=None):
        """Dialog destroy callback"""
        self.destroy()
