# -*- coding:Utf-8 -*-
"""Game edition dialog"""

from gi.repository import Gtk

from lutris.config import LutrisConfig
from lutris.util.log import logger
from lutris.gui.gameconfigvbox import GameConfigVBox
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


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
