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

    def popup(self, event, game_row=None, game=None):
        if game_row:
            game_id = game_row[COL_ID]
            game_slug = game_row[COL_SLUG]
            runner_slug = game_row[COL_RUNNER]
            is_installed = game_row[COL_INSTALLED]
        elif game:
            game_id = game.id
            game_slug = game.slug
            runner_slug = game.runner_name
            is_installed = game.is_installed

        # Clear existing menu
        for item in self.get_children():
            self.remove(item)

        # Main items
        self.add_menuitems(self.main_entries)
        # Runner specific items
        runner_entries = None
        if runner_slug:
            game = game or Game(game_id)
            try:
                runner = runners.import_runner(runner_slug)(game.config)
            except runners.InvalidRunner:
                runner_entries = None
            else:
                runner_entries = runner.context_menu_entries
        if runner_entries:
            self.append(Gtk.SeparatorMenuItem())
            self.add_menuitems(runner_entries)
        self.show_all()

        def manual_script_not_set():
            game = Game(game_id)
            if game.runner:
                return not game.runner.system_config.get("manual_command")

        # Hide some items
        hiding_condition = {
            "add": is_installed,
            "install": is_installed,
            "install_more": not is_installed,
            "play": not is_installed,
            "configure": not is_installed,
            "desktop-shortcut": (
                not is_installed or xdgshortcuts.desktop_launcher_exists(game_slug, game_id)
            ),
            "menu-shortcut": (
                not is_installed or xdgshortcuts.menu_launcher_exists(game_slug, game_id)
            ),
            "rm-desktop-shortcut": (
                not is_installed or not xdgshortcuts.desktop_launcher_exists(game_slug, game_id)
            ),
            "rm-menu-shortcut": (
                not is_installed or not xdgshortcuts.menu_launcher_exists(game_slug, game_id)
            ),
            "browse": not is_installed or runner_slug == "browser",
        }
        # desactivate some items
        desactivate_condition = {"execute-script": manual_script_not_set()}

        for menuitem in self.get_children():
            if not isinstance(menuitem, Gtk.ImageMenuItem):
                continue
            action = menuitem.action_id
            visible = not hiding_condition.get(action)
            sensitive = not desactivate_condition.get(action)
            menuitem.set_sensitive(sensitive)
            menuitem.set_visible(visible)

        super().popup(None, None, None, None, event.button, event.time)
