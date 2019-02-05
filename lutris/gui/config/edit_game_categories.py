import re

from gi.repository import Gtk, Pango

from lutris import pga
from lutris.gui.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
#from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT


class EditGameCategoriesDialog(Dialog, GameDialogCommon):
    """Game category edit dialog."""

    def __init__(self, parent, game):
        super().__init__("Categories - %s" % game.name, parent=parent)
        self.parent = parent

        self.game = game
        self.game_id = game.id
        self.game_categories = pga.get_categories_in_game(self.game_id)
        self.grid = Gtk.Grid()

        self.set_default_size(350, 250)
        self.set_border_width(10)

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)
        self.vbox.pack_start(self._create_category_checkboxes(), True, True, 0)
        self.vbox.pack_start(self._create_add_category(), False, False, 0)

        self.build_action_area(self.on_save)
        self.show_all()

    def _create_category_checkboxes(self):
        frame = Gtk.Frame()
        # frame.set_label("Categories") # probably too much redundancy
        sw = Gtk.ScrolledWindow()
        row = Gtk.VBox()
        for category in pga.get_categories():
            checkbutton_option = Gtk.CheckButton(category)
            if category in self.game_categories:
                checkbutton_option.set_active(True)
            self.grid.attach_next_to(checkbutton_option, None, Gtk.PositionType.BOTTOM, 3, 1)

        row.pack_start(self.grid, True, True, 0)
        sw.add_with_viewport(row)
        frame.add(sw)
        return frame

    def _create_add_category(self):
        def on_add_category(widget=None):
            category_text = category_entry.get_text().strip()
            if category_text != "":
                category_text = re.sub(' +', ' ', category_text)    # Remove excessive whitespaces
                for category_checkbox in self.grid.get_children():
                    if category_checkbox.get_label() == category_text:
                        return
                category_entry.set_text("")
                checkbutton_option = Gtk.CheckButton(category_text)
                checkbutton_option.set_active(True)
                self.grid.attach_next_to(checkbutton_option, None, Gtk.PositionType.TOP, 3, 1)
                pga.add_category(category_text)
                self.vbox.show_all()

        hbox = Gtk.HBox()
        hbox.set_spacing(10)

        category_entry = Gtk.Entry()
        category_entry.set_text("")
        hbox.pack_start(category_entry, True, True, 0)

        button = Gtk.Button.new_with_label("Add Category")
        button.connect("clicked", on_add_category)
        button.set_tooltip_text("Adds the category to the list.")
        hbox.pack_start(button, False, False, 0)

        return hbox

    # Override the save action box, because we don't need the advanced-checkbox
    def build_action_area(self, button_callback, callback2=None):
        self.action_area.set_layout(Gtk.ButtonBoxStyle.END)
        # Buttons
        hbox = Gtk.Box()
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self.on_cancel_clicked)
        hbox.pack_start(cancel_button, True, True, 10)

        save_button = Gtk.Button(label="Save")
        if callback2:
            save_button.connect("clicked", button_callback, callback2)
        else:
            save_button.connect("clicked", button_callback)
        hbox.pack_start(save_button, True, True, 0)
        self.action_area.pack_start(hbox, True, True, 0)

    def is_valid(self):
        return True

    def on_save(self, _button):
        """Save game info and destroy widget. Return True if success."""
        if not self.is_valid():
            return False

        for category_checkbox in self.grid.get_children():
            label = category_checkbox.get_label()
            if label in self.game_categories:
                if not category_checkbox.get_active():
                    pga.delete_game_by_id_from_category(self.game_id, label)
            else:
                if category_checkbox.get_active():
                    pga.add_game_to_category(self.game_id, label)

        self.parent.on_game_updated(self.game)

        self.destroy()
