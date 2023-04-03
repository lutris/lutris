import locale
import re
from gettext import gettext as _

from gi.repository import Gtk

from lutris.database import categories as categories_db
from lutris.gui.config.common import GameDialogCommon


class EditGameCategoriesDialog(GameDialogCommon):
    """Game category edit dialog."""

    def __init__(self, parent, game):
        super().__init__(_("Categories - %s") % game.name, parent=parent)
        self.parent = parent

        self.game = game
        self.game_id = game.id
        self.game_categories = categories_db.get_categories_in_game(self.game_id)
        self.grid = Gtk.Grid()

        self.set_default_size(350, 250)
        self.set_border_width(10)

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)
        self.vbox.pack_start(self._create_category_checkboxes(), True, True, 0)
        self.vbox.pack_start(self._create_add_category(), False, False, 0)

        # Hide advanced-switch since it is unused
        for widget in self.advanced_switch_widgets:
            widget.set_no_show_all(True)
            widget.hide()

        self.show_all()

    def _create_category_checkboxes(self):
        frame = Gtk.Frame()
        # frame.set_label("Categories") # probably too much redundancy
        sw = Gtk.ScrolledWindow()
        row = Gtk.VBox()
        categories = sorted([c for c in categories_db.get_categories() if c['name'] != 'favorite'],
                            key=lambda c: locale.strxfrm(c['name']))
        for category in categories:
            label = category['name']
            checkbutton_option = Gtk.CheckButton(label)
            if label in self.game_categories:
                checkbutton_option.set_active(True)
            self.grid.attach_next_to(checkbutton_option, None, Gtk.PositionType.BOTTOM, 3, 1)

        row.pack_start(self.grid, True, True, 0)
        sw.add_with_viewport(row)
        frame.add(sw)
        return frame

    def _create_add_category(self):
        def on_add_category(widget=None):
            category_text = category_entry.get_text().strip()
            if category_text not in ("", "favorite", "all"):
                category_text = re.sub(' +', ' ', category_text)    # Remove excessive whitespaces
                for category_checkbox in self.grid.get_children():
                    if category_checkbox.get_label() == category_text:
                        return
                category_entry.set_text("")
                checkbutton_option = Gtk.CheckButton(category_text)
                checkbutton_option.set_active(True)
                self.grid.attach_next_to(checkbutton_option, None, Gtk.PositionType.TOP, 3, 1)
                categories_db.add_category(category_text)
                self.vbox.show_all()

        hbox = Gtk.HBox()
        hbox.set_spacing(10)

        category_entry = Gtk.Entry()
        category_entry.set_text("")
        hbox.pack_start(category_entry, True, True, 0)

        button = Gtk.Button.new_with_label(_("Add Category"))
        button.connect("clicked", on_add_category)
        button.set_tooltip_text(_("Adds the category to the list."))
        hbox.pack_start(button, False, False, 0)

        return hbox

    def is_valid(self):
        return True

    def on_save(self, _button):
        """Save game info and destroy widget. Return True if success."""
        if not self.is_valid():
            return False

        for category_checkbox in self.grid.get_children():
            label = category_checkbox.get_label()

            removed_categories = []
            added_categories = []

            if label in self.game_categories:
                if not category_checkbox.get_active():
                    removed_categories.append(label)
            else:
                if category_checkbox.get_active():
                    added_categories.append(label)

            if len(added_categories) > 0 or len(removed_categories) > 0:
                self.game.update_game_categories(added_categories, removed_categories)

        self.parent.on_game_updated(self.game)

        self.destroy()
