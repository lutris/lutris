# -*- coding:Utf-8 -*-
"""Game edition dialog"""
from gi.repository import Gtk

from lutris.config import LutrisConfig
from lutris.util.log import logger
from lutris import pga
from lutris.runners import import_runner
import lutris.runners
from lutris.gui.gameconfigvbox import GameConfigVBox
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


class AddGameDialog(Gtk.Dialog):
    """ Add game dialog class"""
    def __init__(self, parent, game=None):
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

        #Runners: get a list of available runners
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append(("Select a runner from the list", ""))
        for runner_name in lutris.runners.__all__:
            runner_class = import_runner(runner_name)
            runner = runner_class()
            description = runner.description
            if runner.is_installed():
                runner_liststore.append(
                    ("%s (%s)" % (runner_name, description), runner_name)
                )

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

        #add_action = Gtk.Action("Add", )
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
        name = self.realname_entry.get_text()
        self.lutris_config.config["realname"] = name
        self.lutris_config.config["runner"] = self.runner_class

        if self.runner_class and name:

            game_identifier = self.lutris_config.save(config_type="game")
            self.game_info = {"name": name,
                              "runner": self.runner_class,
                              "slug": game_identifier}

            runner = import_runner(self.runner_class)(self.lutris_config)
            self.game_info['directory'] = runner.get_game_path()
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

class EditGameConfigDialog(Gtk.Dialog):
    """Game config edit dialog"""
    def __init__(self, parent, game):
        super(EditGameConfigDialog, self).__init__()
        self.parent_window = parent
        self.game = game
        self.lutris_config = LutrisConfig(game=game)
        game_name = self.lutris_config.config.get("realname", game)
        self.set_title("Edit game configuration for %s" % game_name)
        self.set_size_request(500, 500)

        #Notebook
        notebook = Gtk.Notebook()
        self.vbox.pack_start(notebook, True, True, 0)

        #Game configuration tab
        self.game_config_vbox = GameConfigVBox(self.lutris_config, "game")
        game_config_scrolled_window = Gtk.ScrolledWindow()
        game_config_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                               Gtk.PolicyType.AUTOMATIC)
        game_config_scrolled_window.add_with_viewport(self.game_config_vbox)
        notebook.append_page(game_config_scrolled_window,
                             Gtk.Label(label="Game Configuration"))

        #Runner configuration tab
        self.runner_config_box = RunnerConfigVBox(self.lutris_config, "game")
        runner_config_scrolled_window = Gtk.ScrolledWindow()
        runner_config_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                                 Gtk.PolicyType.AUTOMATIC)
        runner_config_scrolled_window.add_with_viewport(self.runner_config_box)
        notebook.append_page(runner_config_scrolled_window,
                             Gtk.Label(label="Runner Configuration"))

        #System configuration tab
        self.system_config_box = SystemConfigVBox(self.lutris_config, "game")
        system_config_scrolled_window = Gtk.ScrolledWindow()
        system_config_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                                 Gtk.PolicyType.AUTOMATIC)
        system_config_scrolled_window.add_with_viewport(self.system_config_box)
        notebook.append_page(system_config_scrolled_window,
                             Gtk.Label(label="System Configuration"))

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
