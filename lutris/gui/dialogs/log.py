from gi.repository import Gtk
from lutris.gui.widgets.dialogs import Dialog
from lutris.gui.widgets.log_text_view import LogTextView


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
