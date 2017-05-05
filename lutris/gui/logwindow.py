from gi.repository import Gtk
from lutris.gui.widgets import Dialog


class LogWindow(Dialog):
    def __init__(self, title, buffer, parent):
        super(LogWindow, self).__init__(title, parent, 0,
                                        ('_OK', Gtk.ResponseType.OK))
        self.set_size_request(640, 480)
        self.grid = Gtk.Grid()
        self.buffer = buffer
        self.logtextview = Gtk.TextView.new_with_buffer(self.buffer)
        self.logtextview.set_editable(False)
        self.logtextview.set_monospace(True)
        self.logtextview.set_left_margin(10)
        self.logtextview.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.logtextview.get_style_context().add_class('lutris-logview')
        self.logtextview.connect("size-allocate", self.autoscroll)

        scrolledwindow = Gtk.ScrolledWindow(hexpand=True, vexpand=True,
                                            child=self.logtextview)
        self.vbox.add(scrolledwindow)
        self.show_all()

    def autoscroll(self, *args):
        adj = self.logtextview.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
