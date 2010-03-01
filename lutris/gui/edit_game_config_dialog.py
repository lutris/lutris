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

import logging
import gtk
from lutris.config import LutrisConfig
from lutris.game_config_vbox import GameConfigVBox
from lutris.runner_config_vbox import RunnerConfigVBox
from lutris.system_config_vbox import SystemConfigVBox

class EditGameConfigDialog(gtk.Dialog):
    def __init__(self,parent,game):
        self.parent_window = parent
        self.game = game
        gtk.Dialog.__init__(self)
        self.set_title("Edit game configuration")
        self.set_size_request(500,500)
        
        #Top label
        self.lutris_config = LutrisConfig(game=game)
        self.lutris_config.runner = self.lutris_config.config["runner"]
        
        game_name_label = gtk.Label("Edit configuration for %s " % self.lutris_config.config["realname"])
        self.vbox.pack_start(game_name_label,False,False,10)
        
        #Notebook
        config_notebook = gtk.Notebook()
        self.vbox.pack_start(config_notebook)
        
        #Game configuration tab
        self.game_config_vbox = GameConfigVBox(self.lutris_config,"game")
        game_config_scrolled_window = gtk.ScrolledWindow()
        game_config_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        game_config_scrolled_window.add_with_viewport(self.game_config_vbox)
        config_notebook.append_page(game_config_scrolled_window,gtk.Label("Game Configuration"))

        #Runner configuration tab
        self.runner_config_box = RunnerConfigVBox(self.lutris_config,"game")
        runner_config_scrolled_window = gtk.ScrolledWindow()
        runner_config_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        runner_config_scrolled_window.add_with_viewport(self.runner_config_box)
        config_notebook.append_page(runner_config_scrolled_window,gtk.Label("Runner Configuration"))
        
        #System configuration tab
        self.system_config_box = SystemConfigVBox(self.lutris_config,"game")
        system_config_scrolled_window = gtk.ScrolledWindow()
        system_config_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        system_config_scrolled_window.add_with_viewport(self.system_config_box)
        config_notebook.append_page(system_config_scrolled_window,gtk.Label("Runner Configuration"))

        #Action Area
        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        add_button = gtk.Button(None, gtk.STOCK_EDIT)
        self.action_area.pack_start(cancel_button)
        self.action_area.pack_start(add_button)
        cancel_button.connect("clicked", self.close)
        add_button.connect("clicked", self.edit_game)
        
        self.show_all()
        self.run()

    def edit_game(self,widget=None):
        logging.debug(self.lutris_config.config)
        self.lutris_config.save(type="game")
        self.destroy()
        
    def close(self,widget=None):
        self.destroy()
