import re

from gi.repository import Gtk, Pango

from lutris import pga
from lutris.gui.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon

class AddFavoriteGamesDialog(Dialog, GameDialogCommon):
    """Game category edit dialog."""

    def __init__(self, parent, game):
        super().__init__("Favorite Games")
        self.parent = parent

        self.game = game
        self.game_id = game.id
        self.grid = Gtk.Grid()

        self.set_default_size(350, 150)
        self.set_border_width(10)

        favorite_entry_label = Gtk.Label(
            "Do you want to add %s in your favorite games list ? "% game.name, parent=parent
        )
        favorite_entry_label.set_max_width_chars(80)
        favorite_entry_label.set_property("wrap", True)
        self.vbox.add(favorite_entry_label)

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)
        self.vbox.pack_start(self._create_add_favorite(), False, False, 0)

        self.build_action_area(self.on_save)
        self.show_all()

    def _create_add_favorite(self):
        def on_add_favorite(widget=None):
            pga.add_category_favorite()
            pga.add_game_to_category(self.game_id, "favorite")
            self.parent.on_game_updated(self.game)
            self.destroy()

        hbox = Gtk.HBox()
        hbox.set_spacing(10)

        button = Gtk.Button.new_with_label("Add to Favorite Games")
        button.connect("clicked", on_add_favorite)
        button.set_tooltip_text("Adds the Games to the Favorite Games list.")
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
        self.action_area.pack_start(hbox, True, True, 0)
