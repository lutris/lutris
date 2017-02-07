from gi.repository import Gtk
from lutris.gui.widgets import Dialog


class LogTextView(Gtk.TextView):
    def __init__(self, **kwargs):
        super().__init__(editable=False, monospace=True,
                         left_margin=10, wrap_mode=Gtk.WrapMode.CHAR,
                         **kwargs)

        self.get_style_context().add_class('lutris-logview')
        self.set_text = self.props.buffer.set_text


class LogWindow(Dialog):
    def __init__(self, title, parent):
        super(LogWindow, self).__init__(title, parent, 0,
                                        ('_OK', Gtk.ResponseType.OK))
        self.set_size_request(640, 480)
        self.grid = Gtk.Grid()
        self.logtextview = LogTextView()
        scrolledwindow = Gtk.ScrolledWindow(hexpand=True, vexpand=True,
                                            child=self.logtextview)
        self.vbox.add(scrolledwindow)
        self.show_all()
