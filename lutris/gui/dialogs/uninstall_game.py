from gettext import gettext as _

from gi.repository import Gtk, Pango

from lutris.database.games import get_games
from lutris.game import Game
from lutris.gui.dialogs import Dialog, QuestionDialog
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable, reverse_expanduser


class UninstallGameDialog(Dialog):
    def __init__(self, game_id, parent=None):
        super().__init__(parent=parent)
        self.set_size_request(640, 128)
        self.game = Game(game_id)
        self.delete_files = False
        container = Gtk.VBox(visible=True)
        self.get_content_area().add(container)

        title_label = Gtk.Label(visible=True)
        title_label.set_line_wrap(True)
        title_label.set_alignment(0, 0.5)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_markup(_("<span font_desc='14'><b>Uninstall %s</b></span>") % gtk_safe(self.game.name))

        container.pack_start(title_label, False, False, 4)

        self.folder_label = Gtk.Label(visible=True)
        self.folder_label.set_alignment(0, 0.5)

        self.delete_button = Gtk.Button(_("Uninstall"), visible=True)
        self.delete_button.connect("clicked", self.on_delete_clicked)

        if not self.game.directory:
            self.folder_label.set_markup(_("No file will be deleted"))
        elif len(get_games(filters={"directory": self.game.directory, "installed": 1})) > 1:
            self.folder_label.set_markup("The folder %s is used by other games and will be kept." % self.game.directory)
        elif is_removeable(self.game.directory):
            self.delete_button.set_sensitive(False)
            self.folder_label.set_markup(_("<i>Calculating size…</i>"))
            AsyncCall(get_disk_size, self.folder_size_cb, self.game.directory)
        else:
            self.folder_label.set_markup(
                _("Content of %s are protected and will not be deleted.") % reverse_expanduser(self.game.directory)
            )
        container.pack_start(self.folder_label, False, False, 4)

        self.confirm_delete_button = Gtk.CheckButton()
        self.confirm_delete_button.set_active(True)
        container.pack_start(self.confirm_delete_button, False, False, 4)

        button_box = Gtk.HBox(visible=True)
        button_box.set_margin_top(30)
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
        self.folder_label.hide()
        self.confirm_delete_button.show()
        self.confirm_delete_button.set_label(
            _("Delete %s (%s)") % (
                reverse_expanduser(self.game.directory),
                human_size(folder_size)
            )
        )

    def on_close(self, _button):
        self.destroy()

    def on_delete_clicked(self, button):
        button.set_sensitive(False)
        if not self.confirm_delete_button.get_active():
            self.delete_files = False
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
            self.folder_label.set_markup(_("Uninstalling game and deleting files..."))
        else:
            self.folder_label.set_markup(_("Uninstalling game..."))
        self.game.remove(self.delete_files)
        self.destroy()


class RemoveGameDialog(Dialog):
    def __init__(self, game_id, parent=None):
        super().__init__(parent=parent)
        self.set_size_request(640, 128)
        self.game = Game(game_id)
        container = Gtk.VBox(visible=True)
        self.get_content_area().add(container)

        title_label = Gtk.Label(visible=True)
        title_label.set_line_wrap(True)
        title_label.set_alignment(0, 0.5)
        title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_markup(_("<span font_desc='14'><b>Remove %s</b></span>") % gtk_safe(self.game.name))
        container.pack_start(title_label, False, False, 4)

        self.delete_label = Gtk.Label(visible=True)
        self.delete_label.set_alignment(0, 0.5)
        self.delete_label.set_markup(
            _("Completely remove %s from the library?\nAll play time will be lost.") % self.game)
        container.pack_start(self.delete_label, False, False, 4)

        button_box = Gtk.HBox(visible=True)
        button_box.set_margin_top(30)
        style_context = button_box.get_style_context()
        style_context.add_class("linked")
        cancel_button = Gtk.Button(_("Cancel"), visible=True)
        cancel_button.connect("clicked", self.on_close)
        button_box.add(cancel_button)

        self.remove_button = Gtk.Button(_("Remove"), visible=True)
        self.remove_button.connect("clicked", self.on_remove_clicked)

        button_box.add(self.remove_button)
        container.pack_end(button_box, False, False, 0)
        self.show()

    def on_close(self, _button):
        self.destroy()

    def on_remove_clicked(self, button):
        button.set_sensitive(False)
        self.game.delete()
        self.destroy()
