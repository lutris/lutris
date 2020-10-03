from gi.repository import Gtk

from lutris import runners


class ContextualMenu(Gtk.Menu):
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

        menu_item = action.create_menu_item()
        menu_item.action_id = name
        self.append(menu_item)
        return menu_item

    def get_runner_entries(self, game):
        if not game:
            return None
        try:
            runner = runners.import_runner(game.runner_name)(game.config)
        except runners.InvalidRunner:
            return None
        return runner.context_menu_entries

    def popup(self, event, game_actions, game=None, service=None):
        for item in self.get_children():
            self.remove(item)

        for entry in self.main_entries:
            self.add_menuitem(entry)

        if game_actions.game.runner_name and game_actions.game.is_installed:
            runner_entries = self.get_runner_entries(game)
            if runner_entries:
                self.append(Gtk.SeparatorMenuItem())
                for entry in runner_entries:
                    self.add_menuitem(entry)
        self.show_all()

        displayed = game_actions.get_displayed_entries()
        for menuitem in self.get_children():
            if not isinstance(menuitem, Gtk.ImageMenuItem):
                continue
            menuitem.set_visible(displayed.get(menuitem.action_id, True))

        super().popup(None, None, None, None, event.button, event.time)
