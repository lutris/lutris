"""Entry box with popup list and search"""

from gi.repository import Gio, GLib, GObject, Gtk

from lutris.gui.dialogs import display_error


class SearchableEntrybox(Gtk.Box):
    """Entry box with autocompletion and popup list function.
    Well fitted for large lists.
    """

    __gsignals__ = {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, choice_func, initial=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.initial = initial
        self.choice_func = choice_func
        self.liststore = Gtk.ListStore(str, str)
        self.entry = Gtk.Entry()

        # Popover menu for the choice list
        self._popup_menu_model = Gio.Menu()
        self._popup_action_group = Gio.SimpleActionGroup()
        self._popup_popover = None

        self.entry.connect("changed", self.on_entrybox_change)
        self.entry.connect("icon-press", self.on_entrybox_icon_press)
        self.entry.set_hexpand(True)
        self.append(self.entry)
        GLib.idle_add(self._populate_entrybox_choices, choice_func)

    def get_model(self):
        """Proxy to the liststore"""
        return self.liststore

    def get_active_id(self):
        """Return the ID associated with the current entry text."""
        text = self.entry.get_text()
        for row in self.liststore:
            if row[0] == text:
                return row[1]
        return None

    @staticmethod
    def get_has_entry():
        """The entry present is not for editing custom values, only search"""
        return False

    def search_store(self, _completion, string, _iter):
        """Return true if the search string is in the row text."""
        row_text = self.liststore[_iter][0].lower()  # search is always lower case
        return string.lower() in row_text

    def _populate_entrybox_choices(self, choice_func):
        """Populate the liststore and popup menu with choices."""
        try:
            choices = choice_func()
            self._popup_menu_model = Gio.Menu()
            self._popup_action_group = Gio.SimpleActionGroup()

            for idx, choice in enumerate(choices):
                self.liststore.append(choice)
                action_name = "choice_%d" % idx
                action = Gio.SimpleAction.new(action_name, None)
                active_id = choice[1]
                label = choice[0]
                action.connect("activate", lambda _a, _p, aid=active_id, lbl=label: self._on_popup_choice(lbl, aid))
                self._popup_action_group.add_action(action)
                self._popup_menu_model.append(label, "popup." + action_name)

            if self.initial:
                self._set_initial_text()
                self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "emblem-ok-symbolic")
            else:
                self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic")

        except Exception as ex:
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "error-symbolic")
            display_error(ex, parent=self.get_root())

    def _on_popup_choice(self, label, active_id):
        """Handle selection from the popover menu."""
        self.entry.set_text(label)
        self.emit("changed", active_id)
        if self._popup_popover:
            self._popup_popover.popdown()

    def repopulate(self):
        """Clear and repopulate choices; used when an async choices load completes."""
        self.liststore.clear()
        self._populate_entrybox_choices(self.choice_func)

    def on_entrybox_icon_press(self, _entry, _icon_pos):
        """Show popup menu when the primary icon is pressed."""
        self._popup_popover = Gtk.PopoverMenu.new_from_model(self._popup_menu_model)
        self._popup_popover.insert_action_group("popup", self._popup_action_group)
        self._popup_popover.set_parent(self.entry)
        self._popup_popover.popup()

    def _set_initial_text(self):
        """Set the initial text in the entry if it matches an item."""
        for row in self.liststore:
            if row[1] == self.initial:
                self.entry.set_text(row[0])
                break

    def on_entrybox_change(self, _widget):
        """Action triggered on entrybox 'changed' signal."""
        active_id = self.get_active_id()
        self._update_search_icon()
        if active_id:
            self.emit("changed", active_id)

    def _update_search_icon(self):
        """Updates the icon based on the search result."""
        text = self.entry.get_text()
        if not text:
            # No text
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic")
        elif any(row[0] == text for row in self.liststore):
            # Valid option selected
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "emblem-ok-symbolic")
        elif any(text.lower() in row[0].lower() for row in self.liststore):
            # Partial results found
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "content-loading-symbolic")
        else:
            # No results
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "action-unavailable-symbolic")
