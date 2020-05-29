"""Window to show game logs"""
# Third Party Libraries
from gi.repository import Gdk, Gtk

# Lutris Modules
from lutris.gui.widgets.log_text_view import LogTextView


class LogWindow(Gtk.ApplicationWindow):

    def __init__(self, title=None, buffer=None, application=None):
        super().__init__(icon_name="lutris", application=application)
        self.set_title(title)
        self.set_show_menubar(False)

        self.set_size_request(640, 480)
        self.buffer = buffer
        self.logtextview = LogTextView(self.buffer)

        self.vbox = Gtk.VBox(spacing=6)
        self.add(self.vbox)

        scrolledwindow = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=self.logtextview)
        self.vbox.pack_start(scrolledwindow, True, True, 0)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.props.placeholder_text = "Search..."
        self.search_entry.connect("stop-search", self.dettach_search_entry)
        self.search_entry.connect("search-changed", self.logtextview.find_first)
        self.search_entry.connect("next-match", self.logtextview.find_next)
        self.search_entry.connect("previous-match", self.logtextview.find_previous)

        self.connect("key-press-event", self.on_key_press_event)

        self.show_all()

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.search_entry.emit("stop-search")
            return

        ctrl = (event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and event.keyval == Gdk.KEY_f:
            self.attach_search_entry()
            return

        shift = (event.state & Gdk.ModifierType.SHIFT_MASK)
        if event.keyval == Gdk.KEY_Return:
            if shift:
                self.search_entry.emit("previous-match")
            else:
                self.search_entry.emit("next-match")

    def attach_search_entry(self):
        if self.search_entry.props.parent is None:
            self.vbox.pack_start(self.search_entry, False, False, 0)
            self.show_all()
            self.search_entry.grab_focus()
            if len(self.search_entry.get_text()) > 0:
                self.logtextview.find_first(self.search_entry)

    def dettach_search_entry(self, searched_entry):
        if self.search_entry.props.parent is not None:
            self.logtextview.reset_search()
            self.vbox.remove(self.search_entry)
            # Replace to bottom of log
            adj = self.logtextview.get_vadjustment()
            self.logtextview.scroll_max = adj.get_lower()
