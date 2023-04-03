import locale
import re
from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.config.common import GameDialogCommon
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.game import Game


class EditCategoryGamesDialog(GameDialogCommon):
    """Games asigned to category dialog."""

    def __init__(self, parent, category):
        super().__init__(_("Games - %s") % category['name'], parent=parent)
        self.parent = parent

        self.category = category['name']
        self.category_id = category['id']
        self.avaiable_games = [Game(x['id']) for x in games_db.get_games(sorts=[("installed, name", "COLLATE NOCASE DESC")])]
        self.category_games = [Game(x) for x in categories_db.get_game_ids_for_category(self.category)]
        self.grid = Gtk.Grid()

        self.set_default_size(350, 250)
        self.set_border_width(10)

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)
        self.vbox.pack_start(self._create_games_checkboxes(), True, True, 0)

        # Hide advanced-switch since it is unused
        for widget in self.advanced_switch_widgets:
            widget.set_no_show_all(True)
            widget.hide()

        self.show_all()

    def _create_games_checkboxes(self):
        frame = Gtk.Frame()
        sw = Gtk.ScrolledWindow()
        row = Gtk.VBox()
        category_games_names = [x.name for x in self.category_games]
        for game in self.avaiable_games:
            label = game.name
            checkbutton_option = Gtk.CheckButton(label)
            if label in category_games_names:
                checkbutton_option.set_active(True)
            self.grid.attach_next_to(checkbutton_option, None, Gtk.PositionType.BOTTOM, 3, 1)

        row.pack_start(self.grid, True, True, 0)
        sw.add_with_viewport(row)
        frame.add(sw)
        return frame

    def is_valid(self):
        return True

    def on_save(self, _button):
        """Save game info and destroy widget. Return True if success."""
        if not self.is_valid():
            return False

        removed_games = []
        added_games = []
        category_games_names = [x.name for x in self.category_games]
        for game_checkbox in self.grid.get_children():
            label = game_checkbox.get_label()
            game_id = games_db.get_game_by_field(label, 'name')['id']
            if label in category_games_names:
                if not game_checkbox.get_active():
                    removed_games.append(game_id)
            else:
                if game_checkbox.get_active():
                    added_games.append(game_id)

        for game_id in added_games:
            game = Game(game_id)
            game.add_category(self.category)
            self.parent.on_game_updated(game)
        for game_id in removed_games:
            game = Game(game_id)
            game.remove_category(self.category)
            self.parent.on_game_updated(game)

        self.destroy()
