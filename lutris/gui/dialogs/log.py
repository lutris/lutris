"""Window to show game logs"""

import os
from datetime import datetime
from gettext import gettext as _

from gi.repository import Gdk, GObject, Gtk, Pango

from lutris.gui.dialogs import FileDialog
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util import datapath


class LogWindow(GObject.Object):
    def __init__(self, game, buffer, application=None):
        super().__init__()
        ui_filename = os.path.join(datapath.get(), "ui/log-window.ui")
        builder = Gtk.Builder()
        builder.add_from_file(ui_filename)
        builder.connect_signals(self)
        self.window = builder.get_object("log_window")

        self.title = _("Log for {}").format(game)
        self.window.set_title(self.title)

        self.buffer = buffer
        self.logtextview = LogTextView(self.buffer)

        scrolled_window = builder.get_object("scrolled_window")
        scrolled_window.add(self.logtextview)

        self.search_entry = builder.get_object("search_entry")
        self.search_entry.connect("search-changed", self.logtextview.find_first)
        self.search_entry.connect("next-match", self.logtextview.find_next)
        self.search_entry.connect("previous-match", self.logtextview.find_previous)

        save_button = builder.get_object("save_button")
        save_button.connect("clicked", self.on_save_clicked)

        # Add zoom buttons
        zoom_in_button = builder.get_object("zoom_in_button")
        zoom_out_button = builder.get_object("zoom_out_button")
        zoom_in_button.connect("clicked", self.on_zoom_in_clicked)
        zoom_out_button.connect("clicked", self.on_zoom_out_clicked)

        self.window.connect("key-press-event", self.on_key_press_event)
        self.window.show_all()

    def on_key_press_event(self, widget, event):
        shift = event.state & Gdk.ModifierType.SHIFT_MASK
        if event.keyval == Gdk.KEY_Return:
            if shift:
                self.search_entry.emit("previous-match")
            else:
                self.search_entry.emit("next-match")

    def on_save_clicked(self, _button):
        """Handler to save log to a file"""
        now = datetime.now()
        log_filename = "%s (%s).log" % (self.title, now.strftime("%Y-%m-%d-%H-%M"))
        file_dialog = FileDialog(
            message="Save the logs to...", default_path=os.path.expanduser("~/%s" % log_filename), mode="save"
        )
        log_path = file_dialog.filename
        if not log_path:
            return

        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), True)
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(text)

    def on_zoom_in_clicked(self, _button):
        """Increase font size"""
        font = self.logtextview.get_style_context().get_font(Gtk.StateFlags.NORMAL)
        size = font.get_size() / Pango.SCALE
        if size < 48:  # Maximum size
            self.logtextview.override_font(Pango.FontDescription(f"monospace {size + 1}"))

    def on_zoom_out_clicked(self, _button):
        """Decrease font size"""
        font = self.logtextview.get_style_context().get_font(Gtk.StateFlags.NORMAL)
        size = font.get_size() / Pango.SCALE
        if size > 6:  # Minimum size
            self.logtextview.override_font(Pango.FontDescription(f"monospace {size - 1}"))
