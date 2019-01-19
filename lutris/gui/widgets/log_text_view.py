from gi.repository import Gtk


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
