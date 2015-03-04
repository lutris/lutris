from gi.repository import Gtk, Gdk, Pango
from lutris.gui.widgets import Dialog


class LogTextView(Gtk.TextView):
    bg_rgb = 'rgb(47,47,47)'
    fg_rgb = 'rgb(255, 199, 116)'
    font_face = 'Monospace 11'

    def __init__(self):
        super(LogTextView, self).__init__()

        bg_color = Gdk.RGBA()
        bg_color.parse(self.bg_rgb)
        fg_color = Gdk.RGBA()
        fg_color.parse(self.fg_rgb)
        font_description = Pango.FontDescription(self.font_face)

        self.override_color(Gtk.StateFlags.NORMAL, fg_color)
        self.override_color(Gtk.StateFlags.SELECTED, bg_color)
        self.override_background_color(Gtk.StateFlags.NORMAL, bg_color)
        self.override_background_color(Gtk.StateFlags.SELECTED, fg_color)
        self.set_left_margin(10)
        self.set_editable(False)
        self.override_font(font_description)

        self.textbuffer = self.textview.get_buffer()

    def set_text(self, content):
        self.textbuffer.set_text(content)


class LogWindow(Dialog):
    def __init__(self, title, parent):
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_hexpand(True)
        scrolledwindow.set_vexpand(True)
        self.logtextview = LogTextView()
        self.add(scrolledwindow)
        self.add(self.logtextview)
