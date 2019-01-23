"""Window to show game logs"""
from gi.repository import Gtk
from lutris.gui.widgets.log_text_view import LogTextView


class LogWindow(Gtk.ApplicationWindow):
    def __init__(self, title=None, buffer=None, application=None):
        super().__init__(icon_name="lutris", application=application)
        self.set_title(title)
        self.set_show_menubar(False)

        self.set_size_request(640, 480)
        self.buffer = buffer
        self.logtextview = LogTextView(self.buffer)

        scrolledwindow = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True, child=self.logtextview
        )

        self.add(scrolledwindow)
        self.show_all()
