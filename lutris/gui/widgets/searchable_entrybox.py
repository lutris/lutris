"""Entry box with popup list and search"""

from gi.repository import Gdk, GLib, GObject, Gtk

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
        self.liststore = Gtk.ListStore(str, str)
        self.entry = Gtk.Entry()

        self.completion = Gtk.EntryCompletion()
        self.completion.set_model(self.liststore)
        self.completion.set_text_column(0)
        self.completion.set_match_func(self.search_store)
        self.entry.set_completion(self.completion)
        self.popup_menu = Gtk.Menu()

        self.entry.connect("changed", self.on_entrybox_change)
        self.entry.connect("scroll-event", self._on_entrybox_scroll)
        self.entry.connect("icon-press", self.on_entrybox_icon_press)
        self.pack_start(self.entry, True, True, 0)  # Deprecated in Gtk4, use append instead
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
            for choice in choices:
                self.liststore.append(choice)
                menu_item = Gtk.MenuItem(label=choice[0])
                menu_item.connect("activate", self.on_menu_item_activate, choice[1])
                self.popup_menu.append(menu_item)

            if self.initial:
                self._set_initial_text()
                self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "emblem-ok-symbolic")
            else:
                self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic")

            self.popup_menu.show_all()
        except Exception as ex:
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "error-symbolic")
            display_error(ex, parent=self.get_toplevel())  # Deprecated in Gtk4, use get_root instead

    def on_entrybox_icon_press(self, _entry, _icon_pos, _event):
        """Show popup menu when the primary icon is pressed."""
        self.popup_menu.popup_at_widget(self.entry, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)

    def on_menu_item_activate(self, menu_item, active_id):
        """Set the selected item text in the entry and emit the changed signal."""
        self.entry.set_text(menu_item.get_label())
        self.emit("changed", active_id)

    def _set_initial_text(self):
        """Set the initial text in the entry if it matches an item."""
        for row in self.liststore:
            if row[1] == self.initial:
                self.entry.set_text(row[0])
                break

    @staticmethod
    def _on_entrybox_scroll(entrybox, _event):
        """Prevents users from accidentally changing configuration values while scrolling down dialogs."""
        entrybox.stop_emission_by_name("scroll-event")
        return False

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
