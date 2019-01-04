from gi.repository import Gtk
from lutris.gui.widgets.dialogs import Dialog


class LogTextView(Gtk.TextView):
    def __init__(self, buffer, autoscroll=True):
        super().__init__()

        self.set_buffer(buffer)
        self.set_editable(False)
        self.set_monospace(True)
        self.set_left_margin(10)
        self.scroll_max = 0
        self.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.get_style_context().add_class("lutris-logview")
        if autoscroll:
            self.connect("size-allocate", self.autoscroll)

    def autoscroll(self, *args):
        adj = self.get_vadjustment()
        if adj.get_value() == self.scroll_max or self.scroll_max == 0:
            adj.set_value(adj.get_upper() - adj.get_page_size())
            self.scroll_max = adj.get_value()
        else:
            self.scroll_max = adj.get_upper() - adj.get_page_size()


class LogDialog(Dialog):
    def __init__(self, title, buffer, parent):
        super().__init__(title, parent, 0, ("_OK", Gtk.ResponseType.OK))
        self.set_size_request(640, 480)
        self.grid = Gtk.Grid()
        self.buffer = buffer
        self.logtextview = LogTextView(self.buffer)

        scrolledwindow = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True, child=self.logtextview
        )
        self.vbox.add(scrolledwindow)
        self.show_all()
