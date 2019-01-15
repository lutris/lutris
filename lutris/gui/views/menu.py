# pylint: disable=no-member
from gi.repository import Gtk

from lutris.game import Game

from lutris import runners
from lutris.game_actions import GameActions
from lutris.gui.views import COL_ID


class ContextualMenu(Gtk.Menu):
    def __init__(self, main_entries):
        super().__init__()
        self.main_entries = main_entries

    def add_menuitems(self, entries):
        for entry in entries:
            name, label, callback = entry
            action = Gtk.Action(name=name, label=label)
            action.connect("activate", callback)
            menuitem = action.create_menu_item()
            menuitem.action_id = name
            self.append(menuitem)

    def get_runner_entries(self, game):
        try:
            runner = runners.import_runner(game.runner_name)(game.config)
        except runners.InvalidRunner:
            return None
        return runner.context_menu_entries

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

        game_actions = GameActions()
        game_actions.set_game(game=game)

        displayed = game_actions.get_displayed_entries()
        disabled_entries = game_actions.get_disabled_entries()
        for menuitem in self.get_children():
            if not isinstance(menuitem, Gtk.ImageMenuItem):
                continue
            menuitem.set_visible(displayed.get(menuitem.action_id, True))
            menuitem.set_sensitive(not disabled_entries.get(menuitem.action_id))

        super().popup(None, None, None, None, event.button, event.time)
