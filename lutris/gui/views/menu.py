# pylint: disable=no-member
# Third Party Libraries
from gi.repository import GObject, Gtk

# Lutris Modules
from lutris import runners
from lutris.game import Game
from lutris.game_actions import GameActions
from lutris.gui.views import COL_ID
from lutris.util.log import logger


class ContextualMenu(Gtk.Menu):
    __gsignals__ = {
        "shortcut-edited": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
    }

    def __init__(self, main_entries):
        super().__init__()
        self.main_entries = main_entries

    def add_menuitem(self, entry):
        """Add a menu item to the current menu

        Params:
            entry (tuple): tuple containing name, label and callback

        Returns:
            Gtk.MenuItem
        """
        name, label, callback = entry
        action = Gtk.Action(name=name, label=label)
        action.connect("activate", callback)

        if name in ("desktop-shortcut", "rm-desktop-shortcut", "menu-shortcut", "rm-menu-shortcut"):
            action.connect("activate", self.on_shortcut_edited)

        menu_item = action.create_menu_item()
        menu_item.action_id = name
        self.append(menu_item)
        return menu_item

    def get_runner_entries(self, game):
        try:
            runner = runners.import_runner(game.runner_name)(game.config)
        except runners.InvalidRunner:
            return None
        return runner.context_menu_entries

    def popup(self, event, game_row=None, game=None):
        if game_row:
            # FIXME a new game instance is created here, without taking into
            # account running games.
            game = Game(game_row[COL_ID])

        if not game:
            logger.error("No game provided, can't open pop-up menu")
            return

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Main items
        for entry in self.main_entries:
            self.add_menuitem(entry)

        # Runner specific items
        if game.runner_name and game.is_installed:
            runner_entries = self.get_runner_entries(game)
            if runner_entries:
                self.append(Gtk.SeparatorMenuItem())
                for entry in runner_entries:
                    self.add_menuitem(entry)
        self.show_all()

        game_actions = GameActions()
        game_actions.set_game(game=game)

        displayed = game_actions.get_displayed_entries()
        for menuitem in self.get_children():
            if not isinstance(menuitem, Gtk.ImageMenuItem):
                continue
            menuitem.set_visible(displayed.get(menuitem.action_id, True))

        super().popup(None, None, None, None, event.button, event.time)

    def on_shortcut_edited(self, action):
        self.emit('shortcut-edited', action.get_name())
