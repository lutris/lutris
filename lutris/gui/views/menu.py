# pylint: disable=no-member
from gi.repository import Gtk

from lutris.game import Game

from lutris.util import xdgshortcuts
from lutris import runners
from lutris.gui.views import (
    COL_ID,
    COL_SLUG,
    COL_RUNNER,
    COL_INSTALLED
)


class ContextualMenu(Gtk.Menu):
    def __init__(self, main_entries):
        super().__init__()
        self.main_entries = main_entries

    def add_menuitems(self, entries):
        for entry in entries:
            name = entry[0]
            label = entry[1]
            action = Gtk.Action(name=name, label=label)
            action.connect("activate", entry[2])
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)

    def get_runner_entries(self, game):
        try:
            runner = runners.import_runner(game.runner_name)(game.config)
        except runners.InvalidRunner:
            return None
        return runner.context_menu_entries

    @staticmethod
    def get_hidden_entries(game):
        """Return a dictionary of actions that should be hidden for a game"""
        return {
            "add": game.is_installed,
            "install": game.is_installed,
            "install_more": not game.is_installed,
            "play": not game.is_installed,
            "configure": not game.is_installed,
            "desktop-shortcut": (
                not game.is_installed or xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "menu-shortcut": (
                not game.is_installed or xdgshortcuts.menu_launcher_exists(game.slug, game.id)
            ),
            "rm-desktop-shortcut": (
                not game.is_installed or not xdgshortcuts.desktop_launcher_exists(game.slug, game.id)
            ),
            "rm-menu-shortcut": (
                not game.is_installed or not xdgshortcuts.menu_launcher_exists(game.slug, game.id)
            ),
            "browse": not game.is_installed or game.runner_name == "browser",
        }

    @staticmethod
    def get_disabled_entries(game):
        """Return a dictionary of actions that should be disabled for a game"""
        return {
            "execute-script": game.runner and not game.runner.system_config.get("manual_command")
        }

    def popup(self, event, game_row=None, game=None):
        if game_row:
            game = Game(game_row[COL_ID])

        if not game:
            raise ValueError("Missing game")

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Main items
        self.add_menuitems(self.main_entries)
        # Runner specific items
        if game.runner_name and game.is_installed:
            runner_entries = self.get_runner_entries(game)
            if runner_entries:
                self.append(Gtk.SeparatorMenuItem())
                self.add_menuitems(runner_entries)
        self.show_all()

        hidden_entries = self.get_hidden_entries(game)
        disabled_entries = self.get_disabled_entries(game)
        for menuitem in self.get_children():
            if not isinstance(menuitem, Gtk.ImageMenuItem):
                continue
            menuitem.set_visible(not hidden_entries.get(menuitem.action_id))
            menuitem.set_sensitive(not disabled_entries.get(menuitem.action_id))

        super().popup(None, None, None, None, event.button, event.time)
