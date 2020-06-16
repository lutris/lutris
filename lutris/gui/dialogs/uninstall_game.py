# Standard Library
from gettext import gettext as _

# Third Party Libraries
from gi.repository import Gtk, Pango

# Lutris Modules
from lutris.game import Game
from lutris.gui.dialogs import GtkBuilderDialog, QuestionDialog
from lutris.util.system import is_removeable, reverse_expanduser


class UninstallGameDialog(GtkBuilderDialog):
    glade_file = "dialog-uninstall-game.ui"
    dialog_object = "uninstall-game-dialog"

    @staticmethod
    def substitute_label(widget, name, replacement):
        if hasattr(widget, "get_text"):
            get_text = widget.get_text
            set_text = widget.set_text
        elif hasattr(widget, "get_label"):
            get_text = widget.get_label
            set_text = widget.set_label
        else:
            raise TypeError("Unsupported type %s" % type(widget))

        set_text(get_text().replace("{%s}" % name, replacement))

    def initialize(self, game_id=None, callback=None):
        self.game = Game(game_id)
        self.callback = callback
        runner = self.game.runner

        self.substitute_label(self.builder.get_object("description_label"), "game", self.game.name)

        self.substitute_label(
            self.builder.get_object("remove_from_library_button"),
            "game",
            self.game.name,
        )
        remove_contents_button = self.builder.get_object("remove_contents_button")
        if self.game.is_installed:
            path = self.game.directory or ""
            if hasattr(runner, "own_game_remove_method"):
                remove_contents_button.set_label(runner.own_game_remove_method)
                remove_contents_button.set_active(True)
            else:
                try:
                    default_path = runner.default_path
                except AttributeError:
                    default_path = "/"
                if is_removeable(path, excludes=[default_path]):
                    remove_contents_button.set_active(True)
                else:
                    remove_contents_button.set_sensitive(False)
                    path = _("No game folder")

            path = reverse_expanduser(path)
            self.substitute_label(remove_contents_button, "path", path)
            label = remove_contents_button.get_child()
            label.set_use_markup(True)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        else:
            remove_contents_button.hide()

        cancel_button = self.builder.get_object("cancel_button")
        cancel_button.connect("clicked", self.on_close)

        apply_button = self.builder.get_object("apply_button")
        apply_button.connect("clicked", self.on_apply_button_clicked)

    def on_apply_button_clicked(self, widget):
        widget.set_sensitive(False)

        remove_from_library_button = self.builder.get_object("remove_from_library_button")
        remove_from_library = remove_from_library_button.get_active()
        remove_contents_button = self.builder.get_object("remove_contents_button")
        remove_contents = remove_contents_button.get_active()
        if remove_contents and not hasattr(self.game.runner, "no_game_remove_warning"):
            game_dir = self.game.directory.replace("&", "&amp;")
            dlg = QuestionDialog(
                {
                    "question":
                    _("Are you sure you want to delete EVERYTHING under "
                      "\n<b>%s</b>?\n (This can't be undone)") % game_dir,
                    "title":
                    _("CONFIRM DANGEROUS OPERATION"),
                }
            )
            if dlg.result != Gtk.ResponseType.YES:
                widget.set_sensitive(True)
                return

        remove_from_library = self.game.remove(remove_from_library, remove_contents)
        self.callback(self.game.id, remove_from_library)

        self.on_close()
