from gettext import gettext as _

from gi.repository import Gtk, Pango

from lutris.database.games import get_games
from lutris.game import Game
from lutris.gui.dialogs import ModalDialog, QuestionDialog
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import get_disk_size, is_removeable, path_exists, reverse_expanduser


class UninstallGameDialog(ModalDialog):
    def __init__(self, game_id, parent=None):
        super().__init__(parent=parent, border_width=10)
        self.set_size_request(640, 128)
        self.game = Game(game_id)
        self.delete_files = False

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.delete_button = self.add_default_button(_("Uninstall"), Gtk.ResponseType.OK,
                                                     css_class="destructive-action")
        self.connect("response", self.on_response)

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

        if not self.game.directory:
            self.folder_label.set_markup(_("No file will be deleted"))
        elif len(get_games(filters={"directory": self.game.directory})) > 1:
            self.folder_label.set_markup(
                _("The folder %s is used by other games and will be kept.") % self.game.directory)
        elif self.game.config and is_removeable(self.game.directory, self.game.config.system_config):
            self.delete_button.set_sensitive(False)
            self.folder_label.set_markup(_("<i>Calculating size…</i>"))
            AsyncCall(get_disk_size, self.folder_size_cb, self.game.directory)
        elif not path_exists(self.game.directory):
            self.folder_label.set_markup(
                _("%s does not exist.") % reverse_expanduser(self.game.directory)
            )
        else:
            self.folder_label.set_markup(
                _("Content of %s are protected and will not be deleted.") % reverse_expanduser(self.game.directory)
            )
        container.pack_start(self.folder_label, False, False, 4)

        self.confirm_delete_button = Gtk.CheckButton()
        self.confirm_delete_button.set_active(True)
        container.pack_start(self.confirm_delete_button, False, False, 4)

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

    def on_response(self, _widget, response):
        if response == Gtk.ResponseType.OK:
            self.delete_button.set_sensitive(False)
            if not self.confirm_delete_button.get_active():
                self.delete_files = False
            if self.delete_files and not hasattr(self.game.runner, "no_game_remove_warning"):
                dlg = QuestionDialog(
                    {
                        "parent": self,
                        "question": _(
                            "Please confirm.\nEverything under <b>%s</b>\n"
                            "will be deleted."
                        ) % gtk_safe(self.game.directory),
                        "title": _("Permanently delete files?"),
                    }
                )
                if dlg.result != Gtk.ResponseType.YES:
                    self.delete_button.set_sensitive(True)
                    self.stop_emission_by_name("response")
                    return
            if self.delete_files:
                self.folder_label.set_markup(_("Uninstalling game and deleting files..."))
            else:
                self.folder_label.set_markup(_("Uninstalling game..."))
            self.game.remove(self.delete_files)
        self.destroy()


class RemoveGameDialog(ModalDialog):
    def __init__(self, game_id, parent=None):
        super().__init__(parent=parent, border_width=10)
        self.set_size_request(640, 128)
        self.game = Game(game_id)

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.remove_button = self.add_default_button(_("Remove"), Gtk.ResponseType.OK,
                                                     css_class="destructive-action")
        self.connect("response", self.on_response)

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

    def on_response(self, _widget, response):
        if response == Gtk.ResponseType.OK:
            self.remove_button.set_sensitive(False)
            self.game.delete()
        self.destroy()
