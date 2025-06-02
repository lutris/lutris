# pylint: disable=no-member
from gettext import gettext as _
from typing import Dict, Set

from gi.repository import Gtk

from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.game import GAME_UPDATED, Game
from lutris.gui.dialogs import QuestionDialog, SavableModelessDialog
from lutris.util.strings import get_natural_sort_key


class EditCategoryGamesDialog(SavableModelessDialog):
    """Games assigned to category dialog."""

    def __init__(self, parent, category):
        super().__init__(_("Configure %s") % category["name"], parent=parent, border_width=10)

        self.category = category["name"]
        self.category_id = category["id"]
        self.available_games = sorted(
            [Game(x["id"]) for x in games_db.get_games()], key=lambda g: (g.is_installed, get_natural_sort_key(g.name))
        )
        self.category_games = {
            game_id: Game(game_id) for game_id in categories_db.get_game_ids_for_categories([self.category])
        }
        self.grid = Gtk.Grid()

        self.set_default_size(500, 350)

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_label = Gtk.Label(_("Name"))
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(self.category)
        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(self.name_entry, True, True, 0)

        self.vbox.pack_start(name_box, False, False, 0)
        self.vbox.pack_start(self._create_games_checkboxes(), True, True, 0)

        delete_button = self.add_styled_button(Gtk.STOCK_DELETE, Gtk.ResponseType.NONE, css_class="destructive-action")
        delete_button.connect("clicked", self.on_delete_clicked)

        self.show_all()

    def _create_games_checkboxes(self):
        frame = Gtk.Frame()
        sw = Gtk.ScrolledWindow()
        row = Gtk.VBox()
        category_games_names = sorted([x.name for x in self.category_games.values()])
        for game in self.available_games:
            label = game.name
            checkbutton_option = Gtk.CheckButton(label)
            if label in category_games_names:
                checkbutton_option.set_active(True)
            self.grid.attach_next_to(checkbutton_option, None, Gtk.PositionType.BOTTOM, 3, 1)

        row.pack_start(self.grid, True, True, 0)
        sw.add_with_viewport(row)
        frame.add(sw)
        return frame

    def on_delete_clicked(self, _button):
        dlg = QuestionDialog(
            {
                "title": _("Do you want to delete the category '%s'?") % self.category,
                "question": _(
                    "This will permanently destroy the category, but the games themselves will not be deleted."
                ),
                "parent": self,
            }
        )
        if dlg.result == Gtk.ResponseType.YES:
            for game in self.category_games.values():
                game.remove_category(self.category)
            categories_db.remove_category(self.category_id)
            self.destroy()

    def _get_game(self, game_id: str) -> Game:
        if game_id in self.category_games:
            return self.category_games[game_id]
        else:
            return Game(game_id)

    def on_save(self, _button: Gtk.Button) -> None:
        """Save game info and destroy widget."""
        old_name: str = self.category
        new_name: str = categories_db.strip_category_name(self.name_entry.get_text())
        category_games_ids: Set[str] = set(self.category_games.keys())

        # Work out which games hae been added or removed from the category
        unchecked_game_ids: Set[str] = set()
        checked_game_ids: Set[str] = set()
        updated_games: Dict[str, Game] = {}

        for game_checkbox in self.grid.get_children():
            label = game_checkbox.get_label()
            game_id = games_db.get_game_by_field(label, "name")["id"]
            if game_checkbox.get_active():
                checked_game_ids.add(game_id)
            else:
                unchecked_game_ids.add(game_id)

        added_game_ids = checked_game_ids - category_games_ids
        removed_game_ids = unchecked_game_ids & category_games_ids

        # Rename the category if required, and if this is not a merge
        if new_name and old_name != new_name:
            if categories_db.is_reserved_category(new_name):
                raise RuntimeError(_("'%s' is a reserved category name.") % new_name)

            if new_name in (c["name"] for c in categories_db.get_categories()):
                dlg = QuestionDialog(
                    {
                        "title": _("Merge the category '%s' into '%s'?") % (old_name, new_name),
                        "question": _(
                            "If you rename this category, it will be combined with '%s'. Do you want to merge them?"
                        )
                        % new_name,
                        "parent": self,
                    }
                )
                if dlg.result != Gtk.ResponseType.YES:
                    return

                # To merge, remove every categry and add them all to the
                # other one.
                removed_game_ids = category_games_ids
                added_game_ids = checked_game_ids
            else:
                categories_db.redefine_category(self.category_id, new_name)
                old_name = new_name

                updated_games = {
                    game_id: game
                    for game_id, game in self.category_games.items()
                    if game_id not in added_game_ids and game_id not in removed_game_ids
                }

        # Apply category changes and fire GAME_UPDATED as needed after everything
        for game_id in added_game_ids:
            game = self._get_game(game_id)
            game.add_category(new_name, no_signal=True)
            updated_games[game_id] = game

        for game_id in removed_game_ids:
            game = self._get_game(game_id)
            game.remove_category(old_name, no_signal=True)
            updated_games[game_id] = game

        for game in updated_games.values():
            GAME_UPDATED.fire(game)

        self.destroy()
