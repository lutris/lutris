"""Extended combobox with search"""
# Third Party Libraries
# pylint: disable=unsubscriptable-object
from gi.repository import GLib, GObject, Gtk

# Lutris Modules
from lutris.util.jobs import AsyncCall


class SearchableCombobox(Gtk.Bin):

    """Combox box with autocompletion.
    Well fitted for large lists.
    """

    __gsignals__ = {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
    }

    def __init__(self, choice_func, initial=None):
        super().__init__()
        self.initial = initial
        self.liststore = Gtk.ListStore(str, str)
        self.combobox = Gtk.ComboBox.new_with_model_and_entry(self.liststore)
        self.combobox.set_entry_text_column(0)
        self.combobox.set_id_column(1)
        self.combobox.set_valign(Gtk.Align.CENTER)

        completion = Gtk.EntryCompletion()
        completion.set_model(self.liststore)
        completion.set_text_column(0)
        completion.set_match_func(self.search_store)
        completion.connect("match-selected", self.set_id_from_completion)
        entry = self.combobox.get_child()
        entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "content-loading-symbolic")
        entry.set_completion(completion)

        self.combobox.connect("changed", self.on_combobox_change)
        self.combobox.connect("scroll-event", self._on_combobox_scroll)
        self.add(self.combobox)
        GLib.idle_add(self._populate_combobox_choices, choice_func)

    def get_model(self):
        """Proxy to the liststore"""
        return self.liststore

    def get_active(self):
        """Proxy to the get_active method"""
        return self.combobox.get_active()

    @staticmethod
    def get_has_entry():
        """The entry present is not for editing custom values, only search"""
        return False

    def search_store(self, _completion, string, _iter):
        """Return true if any word of a string is present in a row"""
        for word in string.split():
            if word not in self.liststore[_iter][0].lower():  # search is always lower case
                return False
        return True

    def set_id_from_completion(self, _completion, model, _iter):
        """Sets the active ID to the appropriate ID column in the model
        otherwise the value is set to the entry's value.
        """
        self.combobox.set_active_id(model[_iter][1])

    def _populate_combobox_choices(self, choice_func):
        AsyncCall(self._do_populate_combobox_choices, None, choice_func)

    def _do_populate_combobox_choices(self, choice_func):
        for choice in choice_func():
            self.liststore.append(choice)
        entry = self.combobox.get_child()
        entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, None)
        self.combobox.set_active_id(self.initial)

    @staticmethod
    def _on_combobox_scroll(combobox, _event):
        """Prevents users from accidentally changing configuration values
        while scrolling down dialogs.
        """
        combobox.stop_emission_by_name("scroll-event")
        return False

    def on_combobox_change(self, _widget):
        """Action triggered on combobox 'changed' signal."""
        active = self.combobox.get_active()
        if active < 0:
            return
        option_value = self.liststore[active][1]
        self.emit("changed", option_value)
