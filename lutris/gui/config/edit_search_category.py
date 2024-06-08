# pylint: disable=no-member
from gettext import gettext as _

from gi.repository import Gtk

from lutris.database import categories as categories_db
from lutris.gui.dialogs import QuestionDialog, SavableModelessDialog


class EditSearchCategoryDialog(SavableModelessDialog):
    """Games assigned to category dialog."""

    def __init__(self, parent, category):
        super().__init__(_("Configure %s") % category["name"], parent=parent, border_width=10)

        self.category = category["name"]
        self.category_id = category["id"]
        self.search = category["search"]

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
        # self.vbox.pack_start(self._create_games_checkboxes(), True, True, 0)

        delete_button = self.add_styled_button(Gtk.STOCK_DELETE, Gtk.ResponseType.NONE, css_class="destructive-action")
        delete_button.connect("clicked", self.on_delete_clicked)

        self.show_all()

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
            categories_db.remove_category(self.category_id)
            self.destroy()

    def on_save(self, _button: Gtk.Button) -> None:
        """Save game info and destroy widget."""
        old_name: str = self.category
        new_name: str = categories_db.strip_category_name(self.name_entry.get_text())

        # Rename the category if required, and if this is not a merge
        if new_name and old_name != new_name:
            if categories_db.is_reserved_category(new_name):
                raise RuntimeError(_("'%s' is a reserved category name.") % new_name)

            if new_name in (c["name"] for c in categories_db.get_categories()):
                raise RuntimeError(_("'%s' is already a category, and search-based categories can't be merged."))
            else:
                categories_db.rename_category(self.category_id, new_name)

        self.destroy()
