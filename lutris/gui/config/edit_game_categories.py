# pylint: disable=no-member
from gettext import gettext as _
from typing import Sequence

from gi.repository import Gtk

from lutris.database import categories as categories_db
from lutris.database.categories import is_reserved_category
from lutris.game import Game
from lutris.gui.dialogs import QuestionDialog, SavableModelessDialog
from lutris.util.strings import get_natural_sort_key


class EditGameCategoriesDialog(SavableModelessDialog):
    """Game category edit dialog."""

    def __init__(self, game=None, parent=None):
        title = game.name if game else _("Categories")

        super().__init__(title, parent=parent, border_width=10)
        self.set_default_size(350, 250)

        self.category_checkboxes = {}
        self.games = []
        self.categories = sorted(
            [c["name"] for c in categories_db.get_categories() if not is_reserved_category(c["name"])],
            key=lambda c: get_natural_sort_key(c),
        )

        self.checkbox_grid = Gtk.Grid()

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)
        self.vbox.pack_start(self._create_category_checkboxes(), True, True, 0)
        self.vbox.pack_start(self._create_add_category(), False, False, 0)

        if game:
            self.add_games([game])

        self.vbox.show_all()

    def add_games(self, games: Sequence[Game]) -> None:
        """Adds games to the dialog; this is intended to be used when the dialog is for multiple games,
        and can be used more than once to accumulate games."""

        def mark_category_checkbox(checkbox, included):
            # Checks or unchecks a textbox- but after the first game, this will
            # compare against the current state and go to 'inconsistent' rather than
            # reversing the checkbox.
            if len(self.games) == 0:
                checkbox.set_active(included)
            elif not checkbox.get_inconsistent() and checkbox.get_active() != included:
                checkbox.set_active(False)
                checkbox.set_inconsistent(True)

        def add_game(game):
            # Adds a single game to the dialog, and checks or unchecks
            # boxes as appropriate.
            categories = categories_db.get_categories_in_game(game.id)
            other_checkboxes = set(self.category_checkboxes.values())
            for category in categories:
                category_checkbox = self.category_checkboxes.get(category)
                if category_checkbox:
                    other_checkboxes.discard(category_checkbox)
                    mark_category_checkbox(category_checkbox, included=True)

            for category_checkbox in other_checkboxes:
                mark_category_checkbox(category_checkbox, included=False)

            self.games.append(game)

        existing_game_ids = set(game.id for game in self.games)
        for g in games:
            if g.id not in existing_game_ids:
                add_game(g)

        if len(self.games) > 1:
            subtitle = _("%d games") % len(self.games)
            header_bar = self.get_header_bar()
            if header_bar:
                header_bar.set_subtitle(subtitle)

    def _create_category_checkboxes(self):
        """Constructs a frame containing checkboxes for all known (non-special) categories."""
        frame = Gtk.Frame()
        scrolledwindow = Gtk.ScrolledWindow()

        for category in self.categories:
            label = category
            checkbutton = Gtk.CheckButton(label)
            checkbutton.connect("toggled", self.on_checkbutton_toggled)
            self.checkbox_grid.attach_next_to(checkbutton, None, Gtk.PositionType.BOTTOM, 3, 1)
            self.category_checkboxes[category] = checkbutton

        scrolledwindow.add(self.checkbox_grid)
        frame.add(scrolledwindow)
        return frame

    def _create_add_category(self):
        """Creates a box that carries the controls to add a new category."""

        def on_add_category(*_args):
            category = categories_db.strip_category_name(category_entry.get_text())
            if not categories_db.is_reserved_category(category) and category not in self.category_checkboxes:
                category_entry.set_text("")
                checkbutton = Gtk.CheckButton(category, visible=True, active=True)
                self.category_checkboxes[category] = checkbutton
                self.checkbox_grid.attach_next_to(checkbutton, None, Gtk.PositionType.TOP, 3, 1)
                categories_db.add_category(category)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        category_entry = Gtk.Entry()
        category_entry.connect("activate", on_add_category)
        hbox.pack_start(category_entry, True, True, 0)

        button = Gtk.Button.new_with_label(_("Add Category"))
        button.connect("clicked", on_add_category)
        button.set_tooltip_text(_("Adds the category to the list."))
        hbox.pack_end(button, False, False, 0)

        return hbox

    @staticmethod
    def on_checkbutton_toggled(checkbutton):
        # If the user toggles a checkbox, it is no longer inconsistent.
        checkbutton.set_inconsistent(False)

    def on_save(self, _button):
        """Save category changes and destroy widget."""

        changes = []

        for game in self.games:
            for category_checkbox in self.category_checkboxes.values():
                removed_categories = set()
                added_categories = set()

                if not category_checkbox.get_inconsistent():
                    label = category_checkbox.get_label()
                    game_categories = categories_db.get_categories_in_game(game.id)
                    if label in game_categories:
                        if not category_checkbox.get_active():
                            removed_categories.add(label)
                    else:
                        if category_checkbox.get_active():
                            added_categories.add(label)

                if added_categories or removed_categories:
                    changes.append((game, added_categories, removed_categories))

        if changes and len(self.games) > 1:
            if len(changes) == 1:
                question = _("You are updating the categories on 1 game. Are you sure you want to change it?")
            else:
                question = _(
                    "You are updating the categories on %d games. Are you sure you want to change them?"
                ) % len(changes)
            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": question,
                    "title": _("Changing Categories"),
                }
            )
            if dlg.result != Gtk.ResponseType.YES:
                return

        for game, added_categories, removed_categories in changes:
            game.update_game_categories(added_categories, removed_categories)

        self.destroy()
