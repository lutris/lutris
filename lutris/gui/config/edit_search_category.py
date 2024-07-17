# pylint: disable=no-member
from gettext import gettext as _
from typing import Any, Callable, Dict, List, Optional, Tuple

from gi.repository import Gtk

from lutris import runners, services
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.exceptions import InvalidSearchTermError
from lutris.gui.dialogs import QuestionDialog, SavableModelessDialog
from lutris.search import FLAG_TEXTS, GameSearch
from lutris.search_predicate import AndPredicate, SearchPredicate, format_flag


class EditSearchCategoryDialog(SavableModelessDialog):
    """Games assigned to category dialog."""

    def __init__(self, parent, category: Dict[str, Any]) -> None:
        self.category = category.get("name") or "New Category"
        self.category_id = category.get("id")
        self.original_search = category.get("search") or ""
        self.search = self.original_search
        title = _("Configure %s") % self.category

        super().__init__(title, parent=parent, border_width=10)
        self.set_default_size(600, -1)

        self.vbox.set_homogeneous(False)
        self.vbox.set_spacing(10)

        self.name_entry = self._add_entry_box(_("Name"), self.category)
        self.search_entry = self._add_entry_box(_("Search"), self.search)

        self.predicate_widget_functions: Dict[str, Callable[[SearchPredicate], None]] = {}
        self.updating_predicate_widgets = False

        predicates_box = Gtk.Box(Gtk.Orientation.HORIZONTAL)

        self.flags_grid = Gtk.Grid(row_spacing=6, column_spacing=6, margin=6)
        self._add_flag_widgets()

        categories_scrolled_window = Gtk.ScrolledWindow(visible=True)
        categories_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        categories_frame = Gtk.Frame(visible=True)
        categories_frame.get_style_context().add_class("info-frame")
        categories_frame.add(categories_scrolled_window)
        self.categories_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        categories_scrolled_window.add(self.categories_box)
        categories_frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        categories_frame_box.pack_start(Gtk.Label(_("Categories"), halign=Gtk.Align.START), False, False, 0)
        categories_frame_box.pack_start(categories_frame, True, True, 0)

        self._add_category_widgets()

        self.update_predicate_widgets()

        predicates_box.pack_start(self.flags_grid, False, False, 0)
        predicates_box.pack_start(categories_frame_box, True, True, 0)
        self.vbox.pack_start(predicates_box, True, True, 0)

        delete_button = self.add_styled_button(Gtk.STOCK_DELETE, Gtk.ResponseType.NONE, css_class="destructive-action")
        delete_button.connect("clicked", self.on_delete_clicked)
        delete_button.set_sensitive(bool(self.category_id))

        self.show_all()

    def _add_entry_box(self, label: str, text: str) -> Gtk.Entry:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_label = Gtk.Label(label)
        entry = Gtk.Entry()
        entry.set_text(text)
        entry.connect("changed", self.on_search_entry_changed)
        hbox.pack_start(entry_label, False, False, 0)
        hbox.pack_start(entry, True, True, 0)
        self.vbox.pack_start(hbox, False, False, 0)
        return entry

    def on_search_entry_changed(self, _widget):
        self.update_predicate_widgets()

    def update_predicate_widgets(self):
        if not self.updating_predicate_widgets:
            try:
                self.updating_predicate_widgets = True
                search_text = self.search_entry.get_text()
                search = GameSearch(search_text)
                predicate = search.get_predicate()

                for _control, func in self.predicate_widget_functions.items():
                    func(predicate)
            except InvalidSearchTermError:
                pass
            finally:
                self.updating_predicate_widgets = False

    def _add_flag_widgets(self):
        self._add_service_widget(0)
        self._add_runner_widget(1)
        self._add_platform_widget(2)
        self._add_flag_widget(3, _("Installed:"), "installed")
        self._add_flag_widget(4, _("Favorite:"), "favorite")
        self._add_flag_widget(5, _("Hidden:"), "hidden")
        self._add_flag_widget(6, _("Categorized:"), "categorized")

    def _change_search_flag(self, tag: str, flag: Optional[bool]):
        search = GameSearch(self.search)
        p = search.get_flag_predicate(tag, flag)
        if p:
            predicate = search.get_predicate().without_flag(tag)
            predicate = AndPredicate([predicate, p]).simplify()
            self.search = str(predicate)
            self.search_entry.set_text(self.search)

    def _remove_search_flag(self, tag: str):
        search = GameSearch(self.search)
        predicate = search.get_predicate().without_flag(tag)
        self.search = str(predicate)
        self.search_entry.set_text(self.search)

    def _add_flag_widget(self, row, caption, tag):
        def on_combobox_change(_widget):
            if not self.updating_predicate_widgets:
                active_id = combobox.get_active_id()
                if active_id == "omit":
                    self._remove_search_flag(tag)
                else:
                    self._change_search_flag(tag, FLAG_TEXTS[active_id])

        def populate_widget(predicate):
            if predicate.has_flag(tag):
                combobox.set_active_id(format_flag(predicate.get_flag(tag)))
            else:
                combobox.set_active_id("omit")

        label = Gtk.Label(caption, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        self.flags_grid.attach(label, 0, row, 1, 1)

        options = [
            (_("(omit from search)"), "omit"),
            (_("Yes"), "yes"),
            (_("No"), "no"),
            (_("Maybe"), "maybe"),
        ]

        combobox = self._create_combobox(options)
        self.predicate_widget_functions[combobox] = populate_widget
        self.flags_grid.attach(combobox, 1, row, 1, 1)
        combobox.connect("changed", on_combobox_change)

    def _add_service_widget(self, row):
        options = [(s[1]().name, s[0]) for s in services.get_enabled_services().items()]

        self._add_match_widget(
            row, "Source", "source", options, predicate_factory=lambda s, v: s.get_service_predicate(v)
        )

    def _add_runner_widget(self, row):
        options = [(r.human_name, r.name) for r in runners.get_installed()]

        self._add_match_widget(
            row, "Runner", "runner", options, predicate_factory=lambda s, v: s.get_runner_predicate(v)
        )

    def _add_platform_widget(self, row):
        options = [(p, p) for p in games_db.get_used_platforms()]

        self._add_match_widget(
            row, "Platform", "platform", options, predicate_factory=lambda s, v: s.get_platform_predicate(v)
        )

    def _add_match_widget(self, row: int, caption: str, tag: str, options: List[Tuple[str, str]], predicate_factory):
        def on_combobox_change(_widget):
            if not self.updating_predicate_widgets:
                search = GameSearch(self.search)
                predicate = search.get_predicate().without_match(tag)
                active_id = combobox.get_active_id()
                if active_id:
                    p = predicate_factory(search, active_id)
                    predicate = AndPredicate([predicate, p]).simplify()
                self.search = str(predicate)
                self.search_entry.set_text(self.search)

        def populate_widget(predicate):
            matches = predicate.get_matches(tag)
            if matches:
                combobox.set_active_id(matches[0])
            else:
                combobox.set_active_id("")

        label = Gtk.Label(caption, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        self.flags_grid.attach(label, 0, row, 1, 1)

        options = [(_("(omit from search)"), "")] + options
        combobox = self._create_combobox(options)
        self.predicate_widget_functions[combobox] = populate_widget
        self.flags_grid.attach(combobox, 1, row, 1, 1)
        combobox.connect("changed", on_combobox_change)

    def _add_category_widgets(self):
        for category in categories_db.get_categories():
            category_name = category["name"]
            if not categories_db.is_reserved_category(category_name) and not category.get("search"):
                self._add_category_widget(category_name, category_name)

    def _add_category_widget(self, caption, category_name):
        checkbox = Gtk.CheckButton(caption)

        def on_checkbox_toggled(_widget):
            if not self.updating_predicate_widgets:
                search = GameSearch(self.search)
                predicate = search.get_predicate().without_match("category", category_name)
                if checkbox.get_active():
                    p = search.get_category_predicate(category_name)
                    predicate = AndPredicate([predicate, p]).simplify()
                self.search = str(predicate)
                self.search_entry.set_text(self.search)

        def populate_widget(predicate):
            matched = category_name in predicate.get_matches("category")
            checkbox.set_active(matched)

        self.predicate_widget_functions[checkbox] = populate_widget
        self.categories_box.pack_start(checkbox, False, False, 0)
        checkbox.connect("toggled", on_checkbox_toggled)

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

    def _create_combobox(self, options):
        liststore = Gtk.ListStore(str, str)

        for option in options:
            liststore.append(option)

        combobox = Gtk.ComboBox.new_with_model(liststore)
        combobox.set_entry_text_column(0)
        combobox.set_id_column(1)
        combobox.set_halign(Gtk.Align.START)
        combobox.set_valign(Gtk.Align.CENTER)
        renderer_text = Gtk.CellRendererText()
        combobox.pack_start(renderer_text, True)
        combobox.add_attribute(renderer_text, "text", 0)
        return combobox

    def on_save(self, _button: Gtk.Button) -> None:
        """Save game info and destroy widget."""
        old_name: str = self.category
        new_name: str = categories_db.strip_category_name(self.name_entry.get_text())
        old_search: str = self.original_search
        new_search: str = str(GameSearch(self.search_entry.get_text()))

        if not new_name:
            new_name = old_name

        if categories_db.is_reserved_category(new_name):
            raise RuntimeError(_("'%s' is a reserved category name.") % new_name)

        if old_name != new_name:
            if new_name in (c["name"] for c in categories_db.get_categories()):
                raise RuntimeError(_("'%s' is already a category, and search-based categories can't be merged."))

        if not self.category_id:
            # Creating new category!
            categories_db.add_category(category_name=new_name, search=new_search)
        elif old_name != new_name or old_search != new_search:
            # Changing an existing category.
            categories_db.redefine_category(self.category_id, new_name, new_search)

        self.destroy()
