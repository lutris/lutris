# pylint: disable=no-member
from gettext import gettext as _

from gi.repository import Gtk

from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.exceptions import watch_errors
from lutris.game import Game
from lutris.gui.dialogs import ErrorDialog, QuestionDialog, SavableModelessDialog


class EditCategoryGamesDialog(SavableModelessDialog):
    """Games assigned to category dialog."""

    def __init__(self, parent, category):
        super().__init__(_("Configure %s") % category['name'], parent=parent, border_width=10)

        self.category = category['name']
        self.category_id = category['id']
        self.available_games = [Game(x['id']) for x in games_db.get_games(sorts=[("installed", "DESC"),
                                                                                 ("name", "COLLATE NOCASE ASC")
                                                                                 ])]
        self.category_games = [Game(x) for x in categories_db.get_game_ids_for_category(self.category)]
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
        category_games_names = [x.name for x in self.category_games]
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

    @watch_errors()
    def on_delete_clicked(self, _button):
        dlg = QuestionDialog(
            {
                "title": _("Do you want to delete the category '%s'?") % self.category,
                "question": _(
                    "This will permanently destroy the category, but the games themselves will not be deleted."),
                "parent": self
            }
        )
        if dlg.result == Gtk.ResponseType.YES:
            for game in self.category_games:
                game.remove_category(self.category)
            self.destroy()

    @watch_errors()
    def on_save(self, _button):
        """Save game info and destroy widget."""
        removed_games = []
        added_games = []
        new_name = categories_db.strip_category_name(self.name_entry.get_text())

        if not new_name or self.category == new_name:
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

            for game_id in removed_games:
                game = Game(game_id)
                game.remove_category(self.category)
        elif categories_db.is_reserved_category(new_name):
            raise RuntimeError(_("'%s' is a reserved category name.") % new_name)
        else:
            if new_name in (c["name"] for c in categories_db.get_categories()):
                dlg = QuestionDialog(
                    {
                        "title": _("Merge the category '%s' into '%s'?") % (self.category, new_name),
                        "question": _(
                            "If you rename this category, it will be combined with '%s'. "
                            "Do you want to merge them?") % new_name,
                        "parent": self
                    }
                )
                if dlg.result != Gtk.ResponseType.YES:
                    return

            for game in self.category_games:
                game.remove_category(self.category)

            for game_checkbox in self.grid.get_children():
                if game_checkbox.get_active():
                    label = game_checkbox.get_label()
                    game_id = games_db.get_game_by_field(label, 'name')['id']
                    added_games.append(game_id)

            for game_id in added_games:
                game = Game(game_id)
                game.add_category(new_name)

        self.destroy()

    def on_watched_error(self, error):
        ErrorDialog(error, parent=self)
