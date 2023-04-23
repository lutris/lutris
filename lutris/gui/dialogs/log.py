"""Window to show game logs"""
import os
from datetime import datetime
from gettext import gettext as _

from gi.repository import Gdk, GObject, Gtk

from lutris.game import Game
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

        self.game_id = game.id
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

        self.window.connect("key-press-event", self.on_key_press_event)
        self.window.connect("destroy", self.on_destroy)
        self.game_removed_hook_id = GObject.add_emission_hook(Game, "game-removed", self.on_game_removed)
        self.window.show_all()

    def on_key_press_event(self, widget, event):
        shift = event.state & Gdk.ModifierType.SHIFT_MASK
        if event.keyval == Gdk.KEY_Return:
            if shift:
                self.search_entry.emit("previous-match")
            else:
                self.search_entry.emit("next-match")

    def on_game_removed(self, game):
        if str(self.game_id) == str(game.id):
            self.window.destroy()

    def on_save_clicked(self, _button):
        """Handler to save log to a file"""
        now = datetime.now()
        log_filename = "%s (%s).log" % (self.title, now.strftime("%Y-%m-%d-%H-%M"))
        file_dialog = FileDialog(
            message="Save the logs to...",
            default_path=os.path.expanduser("~/%s" % log_filename),
            mode="save"
        )
        log_path = file_dialog.filename
        if not log_path:
            return

        text = self.buffer.get_text(
            self.buffer.get_start_iter(),
            self.buffer.get_end_iter(),
            True
        )
        with open(log_path, "w", encoding='utf-8') as log_file:
            log_file.write(text)

    def on_destroy(self, widget):
        GObject.remove_emission_hook(Game, "game-removed", self.game_removed_hook_id)
