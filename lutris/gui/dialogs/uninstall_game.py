from gettext import gettext as _

from gi.repository import Gtk, Pango

from lutris.database.games import get_games
from lutris.game import Game
from lutris.gui.dialogs import Dialog, NoticeDialog, QuestionDialog
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable, reverse_expanduser


class UninstallGameDialog(Dialog):
    def __init__(self, game_id, callback, parent=None):
        super().__init__(parent=parent)
        self.set_size_request(640, 128)
        self.game = Game(game_id)
        self.callback = callback
        self.delete_files = False
        container = Gtk.VBox(visible=True)
        self.get_content_area().add(container)

        title_label = Gtk.Label(visible=True)
        title_label.set_line_wrap(True)
        title_label.set_alignment(0, 0.5)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_markup("<span font_desc='14'><b>Uninstall %s</b></span>" % gtk_safe(self.game.name))

        container.pack_start(title_label, False, False, 4)

        self.folder_label = Gtk.Label(visible=True)
        self.folder_label.set_alignment(0, 0.5)
        self.folder_label.set_margin_bottom(30)

        self.delete_button = Gtk.Button(_("Uninstall"), visible=True)
        self.delete_button.connect("clicked", self.on_delete_clicked)

        if not self.game.directory:
            self.folder_label.set_markup("No file will be deleted")
        elif len(get_games(searches={"directory": self.game.directory})) > 1:
            self.folder_label.set_markup("The folder %s is used by other games and will be kept." % self.game.directory)
        elif is_removeable(self.game.directory):
            self.delete_button.set_sensitive(False)
            self.folder_label.set_markup("<i>Calculating size…</i>")
            AsyncCall(get_disk_size, self.folder_size_cb, self.game.directory)
        else:
            self.folder_label.set_markup(
                "Content of %s are protected and will not be deleted." % reverse_expanduser(self.game.directory)
            )
        container.pack_start(self.folder_label, False, False, 4)

        button_box = Gtk.HBox(visible=True)
        style_context = button_box.get_style_context()
        style_context.add_class("linked")
        cancel_button = Gtk.Button(_("Cancel"), visible=True)
        cancel_button.connect("clicked", self.on_close)
        button_box.add(cancel_button)
        button_box.add(self.delete_button)
        container.pack_end(button_box, False, False, 0)
        self.show()

    def folder_size_cb(self, folder_size, error):
        if error:
            logger.error(error)
            return
        self.delete_files = True
        self.delete_button.set_sensitive(True)
        self.folder_label.set_markup(
            "This will delete all contents from <b>%s</b> (%s)" % (
                reverse_expanduser(self.game.directory),
                human_size(folder_size)
            )
        )

    def on_close(self, _button):
        self.destroy()

    def on_delete_clicked(self, button):
        button.set_sensitive(False)
        if self.delete_files and not hasattr(self.game.runner, "no_game_remove_warning"):
            dlg = QuestionDialog(
                {
                    "question": _(
                        "Please confirm.\nEverything under <b>%s</b>\n"
                        "will be deleted."
                    ) % gtk_safe(self.game.directory),
                    "title": _("Permanently delete files?"),
                }
            )
            if dlg.result != Gtk.ResponseType.YES:
                button.set_sensitive(True)
                return
        if self.delete_files:
            self.folder_label.set_markup("Uninstalling game and deleting files...")
        else:
            self.folder_label.set_markup("Uninstalling game...")
        AsyncCall(self.game.remove, self.delete_cb, self.delete_files)

    def delete_cb(self, result, error):
        if error:
            logger.error(error)
            NoticeDialog("Something went wrong while deleting the game")
        self.destroy()
