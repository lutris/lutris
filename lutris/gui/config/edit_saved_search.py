# pylint: disable=no-member
from collections.abc import Callable
from copy import copy
from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris import runners, services
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import saved_searches
from lutris.database.saved_searches import SavedSearch
from lutris.exceptions import InvalidSearchTermError
from lutris.gui.dialogs import QuestionDialog, SavableModelessDialog
from lutris.gui.widgets.utils import has_stock_icon
from lutris.search import FLAG_TEXTS, GameSearch
from lutris.search_predicate import AndPredicate, SearchPredicate, format_flag

DEFAULT_NEW_SEARCH_NAME = _("New Saved Search")


class SearchFiltersBox(Gtk.Box):
    """A widget to edit dynamic categories"""

    __gsignals__ = {
        "saved": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(
        self, saved_search: SavedSearch, search_entry: Gtk.SearchEntry | None = None, can_save: bool = True
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.saved_search = copy(saved_search)
        self.original_search = copy(saved_search)

        if not self.saved_search.name:
            self.saved_search.name = DEFAULT_NEW_SEARCH_NAME

        self.search = self.saved_search.search

        self.set_homogeneous(False)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_spacing(10)

        self.name_entry = self._add_entry_box(
            _("Name"),
            self.saved_search.name,
            ["tag-symbolic", "poi-marker", "favorite-symbolic"] if can_save else None,
            self.on_save,
        )

        self.search_entry = search_entry or self._add_entry_box(_("Search"), self.search)
        self.search_entry.connect("changed", self.on_search_entry_changed)

        self.predicate_widget_functions: dict[str, Callable[[SearchPredicate], None]] = {}
        self.updating_predicate_widgets = False

        predicates_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.flags_grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        self._add_flag_widgets()

        categories_scrolled_window = Gtk.ScrolledWindow(visible=True)
        categories_scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        categories_frame = Gtk.Frame(visible=True)
        categories_frame.add_css_class("info-frame")
        categories_frame.set_child(categories_scrolled_window)
        self.categories_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        categories_scrolled_window.set_child(self.categories_box)
        categories_frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        categories_frame_box.append(Gtk.Label(label=_("Categories"), halign=Gtk.Align.START))
        categories_frame.set_hexpand(True)
        categories_frame.set_vexpand(True)
        categories_frame_box.append(categories_frame)

        self._add_category_widgets()

        self.update_predicate_widgets()

        predicates_box.append(self.flags_grid)
        categories_frame_box.set_hexpand(True)
        categories_frame_box.set_vexpand(True)
        predicates_box.append(categories_frame_box)
        predicates_box.set_hexpand(True)
        predicates_box.set_vexpand(True)
        self.append(predicates_box)

    def _add_entry_box(
        self, label: str, text: str, button_icon_names: list[str] | None = None, clicked: Callable | None = None
    ) -> Gtk.Entry:
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_label = Gtk.Label(label=label)
        entry_label.set_halign(Gtk.Align.START)
        entry_label.set_size_request(120, -1)
        entry = Gtk.Entry()
        entry.set_text(text)
        hbox.append(entry_label)
        entry.set_hexpand(True)
        entry.set_vexpand(True)
        hbox.append(entry)

        if button_icon_names:
            button_icon_names = [name for name in button_icon_names if has_stock_icon(name)]
            if button_icon_names:
                button = Gtk.Button.new_from_icon_name(button_icon_names[0])
                button.add_css_class("circular")
                if clicked:
                    button.connect("clicked", clicked)
                hbox.append(button)

        self.append(hbox)
        return entry

    def on_search_entry_changed(self, _widget):
        self.update_predicate_widgets()

    def update_predicate_widgets(self):
        if not self.updating_predicate_widgets:
            try:
                self.updating_predicate_widgets = True
                self.search = self.search_entry.get_text()
                predicate = GameSearch(self.search).get_predicate()

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
        self._add_flag_widget(3, _("Installed"), "installed")
        self._add_flag_widget(4, _("Favorite"), "favorite")
        self._add_flag_widget(5, _("Hidden"), "hidden")
        self._add_flag_widget(6, _("Categorized"), "categorized")

    def _change_search_flag(self, tag: str, flag: bool | None):
        game_search = GameSearch(self.search)
        flag_predicate = game_search.get_flag_predicate(tag, flag)
        if flag_predicate:
            predicate = game_search.get_predicate().without_flag(tag)
            predicate = AndPredicate([predicate, flag_predicate]).simplify()
            self.search = str(predicate)
            self.search_entry.set_text(self.search)

    def _remove_search_flag(self, tag: str):
        predicate = GameSearch(self.search).get_predicate().without_flag(tag)
        self.search = str(predicate)
        self.search_entry.set_text(self.search)

    def _add_flag_widget(self, row, caption, tag):
        def on_combobox_change(_widget):
            if not self.updating_predicate_widgets:
                active_id = combobox.get_active_id()
                if active_id == "":
                    self._remove_search_flag(tag)
                else:
                    self._change_search_flag(tag, FLAG_TEXTS[active_id])

        def populate_widget(predicate):
            if predicate.has_flag(tag):
                combobox.set_active_id(format_flag(predicate.get_flag(tag)))
            else:
                combobox.set_active_id("")

        label = Gtk.Label(label=caption, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        label.set_halign(Gtk.Align.START)
        label.set_size_request(120, -1)
        self.flags_grid.attach(label, 0, row, 1, 1)

        options = [
            (_("-"), ""),
            (_("Yes"), "yes"),
            (_("No"), "no"),
        ]

        combobox = self._create_combobox(options)
        self.predicate_widget_functions[combobox] = populate_widget
        self.flags_grid.attach(combobox, 1, row, 1, 1)
        combobox.connect("changed", on_combobox_change)

    def _add_service_widget(self, row):
        options = [(s[1]().name, s[0]) for s in services.get_enabled_services().items()]
        options.append(("(none)", "none"))

        self._add_match_widget(
            row, _("Source"), "source", options, predicate_factory=lambda s, v: s.get_service_predicate(v)
        )

    def _add_runner_widget(self, row):
        options = [(r.human_name, r.name) for r in runners.get_installed()]
        options.append(("(none)", "none"))

        self._add_match_widget(
            row, _("Runner"), "runner", options, predicate_factory=lambda s, v: s.get_runner_predicate(v)
        )

    def _add_platform_widget(self, row):
        options = [(p, p) for p in games_db.get_used_platforms()]
        options.append(("(none)", "none"))

        self._add_match_widget(
            row, _("Platform"), "platform", options, predicate_factory=lambda s, v: s.get_platform_predicate(v)
        )

    def _add_match_widget(self, row: int, caption: str, tag: str, options: list[tuple[str, str]], predicate_factory):
        def on_combobox_change(_widget):
            if not self.updating_predicate_widgets:
                game_search = GameSearch(self.search)
                predicate = game_search.get_predicate().without_match(tag)
                active_id = combobox.get_active_id()
                if active_id:
                    p = predicate_factory(game_search, active_id)
                    predicate = AndPredicate([predicate, p]).simplify()
                self.search = str(predicate)
                self.search_entry.set_text(self.search)

        def populate_widget(predicate):
            matches = predicate.get_matches(tag)
            if matches:
                combobox.set_active_id(matches[0])
            else:
                combobox.set_active_id("")

        label = Gtk.Label(label=caption, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        self.flags_grid.attach(label, 0, row, 1, 1)

        options = [(_("-"), "")] + options
        combobox = self._create_combobox(options)
        self.predicate_widget_functions[combobox] = populate_widget
        self.flags_grid.attach(combobox, 1, row, 1, 1)
        combobox.connect("changed", on_combobox_change)

    def _add_category_widgets(self):
        for category in categories_db.get_categories():
            category_name = category["name"]
            if not categories_db.is_reserved_category(category_name):
                self._add_category_widget(category_name, category_name)

    def _add_category_widget(self, caption, category_name):
        checkbox = Gtk.CheckButton(label=caption)

        def on_checkbox_toggled(_widget):
            if not self.updating_predicate_widgets:
                game_search = GameSearch(self.search)
                predicate = game_search.get_predicate().without_match("category", category_name)
                if checkbox.get_active():
                    category_predicate = game_search.get_category_predicate(category_name)
                    predicate = AndPredicate([predicate, category_predicate]).simplify()
                self.search = str(predicate)
                self.search_entry.set_text(self.search)

        def populate_widget(predicate):
            matched = category_name in predicate.get_matches("category")
            checkbox.set_active(matched)

        self.predicate_widget_functions[checkbox] = populate_widget
        self.categories_box.append(checkbox)
        checkbox.connect("toggled", on_checkbox_toggled)

    def _create_combobox(self, options):
        liststore = Gtk.ListStore(str, str)

        for option in options:
            liststore.append(option)

        combobox = Gtk.ComboBox.new_with_model(liststore)
        combobox.set_entry_text_column(0)
        combobox.set_id_column(1)
        combobox.set_halign(Gtk.Align.START)
        combobox.set_valign(Gtk.Align.CENTER)
        combobox.set_size_request(240, -1)
        renderer_text = Gtk.CellRendererText()
        combobox.pack_start(renderer_text, True)
        combobox.add_attribute(renderer_text, "text", 0)
        return combobox

    @property
    def search_name(self):
        name = self.name_entry.get_text() or self.original_search.name
        return saved_searches.strip_saved_search_name(name)

    @search_name.setter
    def search_name(self, value):
        value = saved_searches.strip_saved_search_name(value)
        self.name_entry.set_text(value)
        self.saved_search.name = value

    def on_save(self, _button: Gtk.Button) -> None:
        """Save game info and destroy widget."""
        search_name = self.search_name
        self.saved_search.name = search_name
        self.saved_search.search = str(GameSearch(self.search_entry.get_text()))

        if self.original_search.name != self.saved_search.name:
            if saved_searches.get_saved_search_by_name(self.saved_search.name):
                raise RuntimeError(_("'%s' is already a saved search.") % self.saved_search.name)

        if not self.saved_search.saved_search_id:
            # Creating new search!
            self.saved_search.add()
        elif self.original_search != self.saved_search:
            # Changing an existing search.
            self.saved_search.update()

        self.search_name = DEFAULT_NEW_SEARCH_NAME
        self.emit("saved", search_name)


class EditSavedSearchDialog(SavableModelessDialog):
    """A dialog to edit saved searches."""

    def __init__(self, parent, saved_search: SavedSearch) -> None:
        self.filter_box = SearchFiltersBox(saved_search, can_save=False)
        self.saved_search = copy(saved_search)
        self.original_search = copy(saved_search)

        if not self.saved_search.name:
            self.saved_search.name = DEFAULT_NEW_SEARCH_NAME
        title = _("Configure %s") % self.saved_search.name
        super().__init__(title, parent=parent, border_width=10)
        self.set_default_size(600, -1)

        content_area = self.get_content_area()
        content_area.set_homogeneous(False)
        content_area.set_spacing(10)
        self.filter_box.set_hexpand(True)
        self.filter_box.set_vexpand(True)
        content_area.append(self.filter_box)

        delete_button = self.add_styled_button(_("Delete"), Gtk.ResponseType.NONE, css_class="destructive-action")
        delete_button.connect("clicked", self.on_delete_clicked)
        delete_button.set_visible(bool(self.saved_search.saved_search_id))

    def on_save(self, button: Gtk.Button) -> None:
        """Save game info and destroy widget."""
        self.filter_box.on_save(button)
        self.destroy()

    def on_delete_clicked(self, _button):
        dlg = QuestionDialog(
            {
                "title": _("Do you want to delete the saved search '%s'?") % self.original_search.name,
                "question": _(
                    "This will permanently destroy the saved search, but the games themselves will not be deleted."
                ),
                "parent": self,
            }
        )
        if dlg.result == Gtk.ResponseType.YES:
            self.saved_search.remove()
            self.destroy()
