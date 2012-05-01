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

import gtk

import lutris.runners
from lutris.runners import import_runner
from lutris.config import LutrisConfig
from lutris.util.log import logger

from lutris.gui.gameconfigvbox import GameConfigVBox
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


# pylint: disable=R0904
class AddGameDialog(gtk.Dialog):
    """ Add game dialog class"""
    def __init__(self, parent):
        super(AddGameDialog, self).__init__()
        self.parent_window = parent

        #Real name
        realname_hbox = gtk.HBox()
        realname_label = gtk.Label("Name")
        realname_hbox.pack_start(realname_label, False, False, 5)
        self.realname_entry = gtk.Entry()
        realname_hbox.pack_start(self.realname_entry)
        self.vbox.pack_start(realname_hbox, False, False, 5)
        self.lutris_config = LutrisConfig()

        self.set_title("Add a new game")
        self.set_size_request(600, 500)
        #Runner
        #get a list of available runners
        runner_liststore = gtk.ListStore(str, str)
        runner_liststore.append(("Choose a runner for the list", ""))
        for runner_name in lutris.runners.__all__:
            runner_cls = import_runner(runner_name)
            runner = runner_cls()
            if hasattr(runner, "description"):
                description = runner.description
            else:
                logger.debug("Please fix %s and add a description attribute",
                             runner_cls)
                description = ""
            if hasattr(runner, "machine"):
                machine = runner.machine
            else:
                logger.debug("Please fix % and add a machine attribute",
                             runner_cls)
                machine = ""
            if runner.is_installed():
                runner_liststore.append((machine + " (" + description + ")",
                                         runner_name))

        runner_combobox = gtk.ComboBox(runner_liststore)
        runner_combobox.connect("changed", self.on_runner_changed)
        cell = gtk.CellRendererText()
        runner_combobox.pack_start(cell, True)
        runner_combobox.add_attribute(cell, 'text', 0)
        self.vbox.pack_start(runner_combobox, False, True, 5)

        notebook = gtk.Notebook()
        self.vbox.pack_start(notebook)

        #Game configuration
        self.game_config_vbox = gtk.Label("Select a runner from the list")
        self.conf_scroll_window = gtk.ScrolledWindow()
        self.conf_scroll_window.set_policy(gtk.POLICY_AUTOMATIC,
                                           gtk.POLICY_AUTOMATIC)
        self.conf_scroll_window.add_with_viewport(self.game_config_vbox)
        notebook.append_page(self.conf_scroll_window,
                                  gtk.Label("Game configuration"))

        #Runner configuration
        self.runner_config_vbox = gtk.Label("Select a runner from the list")
        self.runner_scroll_window = gtk.ScrolledWindow()
        self.runner_scroll_window.set_policy(gtk.POLICY_AUTOMATIC,
                                             gtk.POLICY_AUTOMATIC)
        self.runner_scroll_window.add_with_viewport(self.runner_config_vbox)
        notebook.append_page(self.runner_scroll_window,
                                  gtk.Label("Runner configuration"))

        #System configuration
        self.system_config_vbox = SystemConfigVBox(self.lutris_config, "game")
        self.system_scroll_window = gtk.ScrolledWindow()
        self.system_scroll_window.set_policy(gtk.POLICY_AUTOMATIC,
                                             gtk.POLICY_AUTOMATIC)
        self.system_scroll_window.add_with_viewport(self.system_config_vbox)
        notebook.append_page(self.system_scroll_window,
                                  gtk.Label("System configuration"))

        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        add_button = gtk.Button(None, gtk.STOCK_ADD)
        self.action_area.pack_start(cancel_button)
        self.action_area.pack_start(add_button)
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
        logger.debug("saving")
        logger.debug(self.lutris_config.config)
        logger.debug(self.lutris_config.game_config)

        if self.runner_class and realname:
            game_identifier = self.lutris_config.save(config_type="game")
            self.game_info = {"name": realname,
                              "runner": self.runner_class,
                              "id": game_identifier}
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
            no_runner_label = gtk.Label("Choose a runner from the list")
            no_runner_label.show()
            self.runner_scroll_window.add_with_viewport(no_runner_label)
            return

        self.runner_class = widget.get_model()[selected_runner][1]
        self.lutris_config = LutrisConfig(self.runner_class)
        logger.debug("loading config before adding game : ")
        logger.debug(self.lutris_config.config)
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
