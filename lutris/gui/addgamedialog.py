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

"""Dialog to add a game manually"""

from gi.repository import Gtk

import lutris.runners
from lutris import pga
from lutris.runners import import_runner
from lutris.config import LutrisConfig
#from lutris.util.log import logger

from lutris.gui.gameconfigvbox import GameConfigVBox
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


class AddGameDialog(Gtk.Dialog):
    """ Add game dialog class"""
    def __init__(self, parent):
        super(AddGameDialog, self).__init__()
        self.parent_window = parent

        #Real name
        realname_hbox = Gtk.HBox()
        realname_label = Gtk.Label(label="Name")
        realname_hbox.pack_start(realname_label, False, False, 5)
        self.realname_entry = Gtk.Entry()
        realname_hbox.add(self.realname_entry)
        self.vbox.pack_start(realname_hbox, False, False, 5)
        self.lutris_config = LutrisConfig()

        self.set_title("Add a new game")
        self.set_size_request(600, 500)
        #Runner
        #get a list of available runners
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append(("Select a runner from the list", ""))
        for runner_name in lutris.runners.__all__:
            runner_class = import_runner(runner_name)
            runner = runner_class()
            description = runner.description
            if runner.is_installed():
                runner_liststore.append(("%s (%s)" % (runner_name,
                                                      description),
                                         runner_name))

        runner_combobox = Gtk.ComboBox.new_with_model(runner_liststore)
        runner_combobox.connect("changed", self.on_runner_changed)
        cell = Gtk.CellRendererText()
        runner_combobox.pack_start(cell, True)
        runner_combobox.add_attribute(cell, 'text', 0)
        self.vbox.pack_start(runner_combobox, False, True, 5)

        notebook = Gtk.Notebook()
        self.vbox.pack_start(notebook, True, True, 0)

        default_label = "Select a runner from the list"
        #Game configuration
        self.game_config_vbox = Gtk.Label(label=default_label)
        self.conf_scroll_window = Gtk.ScrolledWindow()
        self.conf_scroll_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                           Gtk.PolicyType.AUTOMATIC)
        self.conf_scroll_window.add_with_viewport(self.game_config_vbox)
        notebook.append_page(self.conf_scroll_window,
                             Gtk.Label(label="Game configuration"))

        #Runner configuration
        self.runner_config_vbox = Gtk.Label(label=default_label)
        self.runner_scroll_window = Gtk.ScrolledWindow()
        self.runner_scroll_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                             Gtk.PolicyType.AUTOMATIC)
        self.runner_scroll_window.add_with_viewport(self.runner_config_vbox)
        notebook.append_page(self.runner_scroll_window,
                             Gtk.Label(label="Runner configuration"))

        #System configuration
        self.system_config_vbox = SystemConfigVBox(self.lutris_config, "game")
        self.system_scroll_window = Gtk.ScrolledWindow()
        self.system_scroll_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                             Gtk.PolicyType.AUTOMATIC)
        self.system_scroll_window.add_with_viewport(self.system_config_vbox)
        notebook.append_page(self.system_scroll_window,
                             Gtk.Label(label="System configuration"))

        cancel_button = Gtk.Button(None, Gtk.STOCK_CANCEL)
        add_button = Gtk.Button(None, Gtk.STOCK_ADD)
        self.action_area.add(cancel_button)
        self.action_area.add(add_button)
        cancel_button.connect("clicked", self.close)
        add_button.connect("clicked", self.add_game)

        self.show_all()
        self.run()

    def add_game(self, _button):
        """OK button pressed in the Add Game Dialog"""
        #Get name
        realname = self.realname_entry.get_text()
        #Get runner
        self.lutris_config.config["realname"] = realname
        self.lutris_config.config["runner"] = self.runner_class

        if self.runner_class and realname:
            game_identifier = self.lutris_config.save(config_type="game")
            self.game_info = {"name": realname,
                              "runner": self.runner_class,
                              "slug": game_identifier}
            pga.add_game(**self.game_info)
            self.destroy()

    def on_runner_changed(self, widget):
        """Action called when runner drop down is changed"""
        selected_runner = widget.get_active()
        scroll_windows_children = [self.conf_scroll_window.get_children(),
                                   self.runner_scroll_window.get_children(),
                                   self.system_scroll_window.get_children()]
        for scroll_window_children in scroll_windows_children:
            for child in scroll_window_children:
                child.destroy()

        if selected_runner == 0:
            no_runner_label = Gtk.Label(label="Choose a runner from the list")
            no_runner_label.show()
            self.runner_scroll_window.add_with_viewport(no_runner_label)
            return

        self.runner_class = widget.get_model()[selected_runner][1]
        self.lutris_config = LutrisConfig(self.runner_class)
        self.game_config_vbox = GameConfigVBox(self.lutris_config, "game")
        self.conf_scroll_window.add_with_viewport(self.game_config_vbox)
        self.conf_scroll_window.show_all()

        #Load runner box
        self.runner_options_vbox = RunnerConfigVBox(self.lutris_config, "game")
        self.runner_scroll_window.add_with_viewport(self.runner_options_vbox)
        self.runner_scroll_window.show_all()

        #Load system box
        self.system_config_vbox = SystemConfigVBox(self.lutris_config, "game")
        self.system_scroll_window.add_with_viewport(self.system_config_vbox)
        self.system_scroll_window.show_all()

    def close(self, _widget=None, _other=None):
        """Action received on dialog close"""
        self.destroy()
