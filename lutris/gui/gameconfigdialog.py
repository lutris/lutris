# -*- coding:Utf-8 -*-
"""Game edition dialog"""
from gi.repository import Gtk

from lutris.config import LutrisConfig
from lutris.util.log import logger
from lutris import pga
import lutris.runners
from lutris.gui.gameconfigvbox import GameConfigVBox
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


class GameDialogCommon(object):

    def build_name_entry(self):
        name_box = Gtk.HBox()
        name_label = Gtk.Label(label="Name")
        name_box.pack_start(name_label, False, False, 5)
        self.realname_entry = Gtk.Entry()
        name_box.add(self.realname_entry)
        self.vbox.pack_start(name_box, False, False, 5)

    @staticmethod
    def get_runner_liststore():
        """ Build a ListStore with available runners. """
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append(("Select a runner from the list", ""))
        for runner_name in lutris.runners.__all__:
            runner_class = lutris.runners.import_runner(runner_name)
            runner = runner_class()
            if runner.is_installed():
                description = runner.description
                runner_liststore.append(
                    ("%s (%s)" % (runner_name, description), runner_name)
                )
        return runner_liststore

    @staticmethod
    def build_scrolled_window(widget):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add_with_viewport(widget)
        scrolled_window.show_all()
        return scrolled_window

    def build_runner_dropdown(self):
        runner_liststore = self.get_runner_liststore()
        runner_combobox = Gtk.ComboBox.new_with_model(runner_liststore)
        runner_combobox.connect("changed", self.on_runner_changed)
        cell = Gtk.CellRendererText()
        runner_combobox.pack_start(cell, True)
        runner_combobox.add_attribute(cell, 'text', 0)
        self.vbox.pack_start(runner_combobox, False, True, 5)

    def build_notebook(self):
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 0)

    def add_notebook_tab(self, widget, label):
        self.notebook.append_page(widget, Gtk.Label(label=label))

    def build_game_tab(self):
        self.game_box = GameConfigVBox(self.lutris_config, "game")
        game_sw = self.build_scrolled_window(self.game_box)
        self.add_notebook_tab(game_sw, "Game configuration")

    def build_runner_tab(self):
        self.runner_box = RunnerConfigVBox(self.lutris_config, "game")
        self.runner_sw = self.build_scrolled_window(self.runner_box)
        self.add_notebook_tab(self.runner_sw, "Runner configuration")

    def build_system_tab(self):
        self.system_box = SystemConfigVBox(self.lutris_config, "game")
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.add_notebook_tab(self.system_sw, "System configuration")

    def on_cancel_clicked(self, widget=None):
        """ Dialog destroy callback """
        self.destroy()


class AddGameDialog(Gtk.Dialog, GameDialogCommon):
    """ Add game dialog class"""
    def __init__(self, parent, game=None):
        super(AddGameDialog, self).__init__()
        self.parent_window = parent
        self.lutris_config = LutrisConfig()

        self.set_title("Add a new game")
        self.set_size_request(600, 500)

        self.build_name_entry()
        self.build_runner_dropdown()
        self.build_notebook()

        #Game configuration
        default_label = "Select a runner from the list"
        self.game_box = Gtk.Label(label=default_label)
        self.game_sw = self.build_scrolled_window(self.game_box)
        self.add_notebook_tab(self.game_sw, "Game configuration")

        #Runner configuration
        self.runner_box = Gtk.Label(label=default_label)
        self.runner_sw = self.build_scrolled_window(self.runner_box)
        self.add_notebook_tab(self.runner_sw, "Runner configuration")

        #System configuration
        self.system_box = SystemConfigVBox(self.lutris_config, "game")
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.add_notebook_tab(self.system_sw, "System configuration")

        cancel_button = Gtk.Button(None, Gtk.STOCK_CANCEL)
        cancel_button.connect("clicked", self.on_cancel_clicked)
        self.action_area.add(cancel_button)

        add_button = Gtk.Button(None, Gtk.STOCK_ADD)
        add_button.connect("clicked", self.add_game)
        self.action_area.add(add_button)

        self.show_all()
        self.run()

    def add_game(self, _button):
        """OK button pressed in the Add Game Dialog"""
        name = self.realname_entry.get_text()
        self.lutris_config.config["realname"] = name
        self.lutris_config.config["runner"] = self.runner_name

        if self.runner_name and name:

            game_identifier = self.lutris_config.save(config_type="game")
            self.game_info = {"name": name,
                              "runner": self.runner_name,
                              "slug": game_identifier}
            runner_class = lutris.runners.import_runner(self.runner_name)
            runner = runner_class(self.lutris_config)
            self.game_info['directory'] = runner.get_game_path()
            pga.add_game(**self.game_info)
            self.destroy()

    def on_runner_changed(self, widget):
        """Action called when runner drop down is changed"""
        runner_index = widget.get_active()
        self.notebook.remove_page(2)
        self.notebook.remove_page(1)
        self.notebook.remove_page(0)

        if runner_index == 0:
            no_runner_label = Gtk.Label(label="Choose a runner from the list")
            no_runner_label.show()
            self.runner_sw.add_with_viewport(no_runner_label)
            return

        self.runner_name = widget.get_model()[runner_index][1]
        self.lutris_config = LutrisConfig(self.runner_name)

        self.build_game_tab()
        self.build_runner_tab()
        self.build_system_tab()


class EditGameConfigDialog(Gtk.Dialog, GameDialogCommon):
    """ Game config edit dialog """
    def __init__(self, parent, game):
        super(EditGameConfigDialog, self).__init__()
        self.parent_window = parent
        self.game = game
        self.lutris_config = LutrisConfig(game=game)
        game_name = self.lutris_config.config.get("realname", game)
        self.set_title("Edit game configuration for %s" % game_name)
        self.set_size_request(500, 500)

        self.build_notebook()
        self.build_game_tab()
        self.build_runner_tab()
        self.build_system_tab()

        #Action Area
        cancel_button = Gtk.Button(None, Gtk.STOCK_CANCEL)
        cancel_button.connect("clicked", self.on_cancel_clicked)
        self.action_area.pack_start(cancel_button, True, True, 0)

        add_button = Gtk.Button(None, Gtk.STOCK_EDIT)
        add_button.connect("clicked", self.edit_game)
        self.action_area.pack_start(add_button, True, True, 0)

        self.show_all()
        self.run()

    def edit_game(self, _widget=None):
        """Save the changes"""
        logger.debug(self.lutris_config.config)
        self.lutris_config.save(config_type="game")
        self.destroy()
