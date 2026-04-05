"""Window to show game logs"""

import os
from datetime import datetime
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import GObject, Gtk

from lutris.gui.dialogs import FileDialog
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.util import datapath

if TYPE_CHECKING:
    from lutris.game import Game
    from lutris.gui.application import LutrisApplication


class LogWindow(GObject.Object):
    def __init__(self, game: "Game", buffer: Gtk.TextBuffer, application: "LutrisApplication | None" = None):
        super().__init__()
        ui_filename = os.path.join(datapath.get(), "ui/log-window.ui")
        builder = Gtk.Builder()
        builder.add_from_file(ui_filename)
        self.window: Gtk.ApplicationWindow = builder.get_object("log_window")

        self.title = _("Log for {}").format(game)
        self.window.set_title(self.title)

        self.buffer = buffer
        self.logtextview = LogTextView(self.buffer)
        self.font_size = 10
        self.font_css_provider = Gtk.CssProvider()
        self.logtextview.get_style_context().add_provider(
            self.font_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        scrolled_window: Gtk.ScrolledWindow = builder.get_object("scrolled_window")
        scrolled_window.set_child(self.logtextview)

        self.search_entry: Gtk.SearchEntry = builder.get_object("search_entry")
        self.search_entry.connect("search-changed", self.logtextview.find_first)
        self.search_entry.connect("next-match", self.logtextview.find_next)
        self.search_entry.connect("previous-match", self.logtextview.find_previous)

        save_button: Gtk.Button = builder.get_object("save_button")
        save_button.connect("clicked", self.on_save_clicked)

        # Add zoom buttons
        zoom_in_button: Gtk.Button = builder.get_object("zoom_in_button")
        zoom_out_button: Gtk.Button = builder.get_object("zoom_out_button")
        zoom_in_button.connect("clicked", self.on_zoom_in_clicked)
        zoom_out_button.connect("clicked", self.on_zoom_out_clicked)

        # TODO: key-press-event removed in GTK4; need EventControllerKey
        # self.window.connect("key-press-event", self.on_key_press_event)

        if application:
            self.window.set_application(application)
        self.window.present()

    def on_save_clicked(self, _button: Gtk.Button) -> None:
        """Handler to save log to a file"""
        now = datetime.now()
        log_filename = "%s (%s).log" % (self.title, now.strftime("%Y-%m-%d-%H-%M"))
        file_dialog = FileDialog(
            message="Save the logs to...", default_path=os.path.expanduser("~/%s" % log_filename), mode="save"
        )
        log_path = file_dialog.filename
        if not log_path:
            return None

        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), True)
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(text)

    def _update_font_size(self):
        css = "textview { font-size: %dpt; }" % self.font_size
        self.font_css_provider.load_from_string(css)

    def on_zoom_in_clicked(self, _button: Gtk.Button) -> None:
        """Increase font size"""
        self.font_size = min(self.font_size + 1, 36)
        self._update_font_size()

    def on_zoom_out_clicked(self, _button: Gtk.Button) -> None:
        """Decrease font size"""
        self.font_size = max(self.font_size - 1, 6)
        self._update_font_size()
