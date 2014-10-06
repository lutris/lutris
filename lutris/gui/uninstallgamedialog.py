from gi.repository import Gtk
from lutris.gui.dialogs import GtkBuilderDialog
from lutris.game import Game
from lutris.util.system import is_removeable
from lutris.gui.dialogs import QuestionDialog


class UninstallGameDialog(GtkBuilderDialog):
    glade_file = 'dialog-uninstall-game.ui'
    dialog_object = 'uninstall-game-dialog'

    def substitute_label(self, widget, name, replacement):
        if hasattr(widget, 'get_text'):
            get_text = widget.get_text
            set_text = widget.set_text
        elif hasattr(widget, 'get_label'):
            get_text = widget.get_label
            set_text = widget.set_label
        else:
            raise TypeError("Unsupported type %s" % type(widget))

        set_text(get_text().replace("{%s}" % name, replacement))

    def initialize(self, slug=None, callback=None):
        self.game = Game(slug)
        self.callback = callback

        self.substitute_label(self.builder.get_object('description_label'),
                              'game', self.game.name)

        self.substitute_label(
            self.builder.get_object('remove_from_library_button'),
            'game', self.game.name
        )
        remove_contents_button = self.builder.get_object(
            'remove_contents_button'
        )
        try:
            default_path = self.game.runner.default_path
        except AttributeError:
            default_path = "/"
        if not is_removeable(self.game.directory, excludes=[default_path])\
           or not self.game.is_installed:
            remove_contents_button.set_sensitive(False)
        path = self.game.directory or 'disk'
        self.substitute_label(remove_contents_button, 'path', path)
        remove_contents_button.get_children()[0].set_use_markup(True)

        cancel_button = self.builder.get_object('cancel_button')
        cancel_button.connect('clicked', self.on_close)

        apply_button = self.builder.get_object('apply_button')
        apply_button.connect('clicked', self.on_apply_button_clicked)

    def on_apply_button_clicked(self, widget):
        widget.set_sensitive(False)

        remove_from_library_button = self.builder.get_object(
            'remove_from_library_button'
        )
        remove_from_library = remove_from_library_button.get_active()
        remove_contents_button = self.builder.get_object(
            'remove_contents_button'
        )
        remove_contents = remove_contents_button.get_active()
        if remove_contents:
            dlg = QuestionDialog({
                'question': "Are you sure you want to delete EVERYTHING under "
                            "\n<b>%s</b>?\n (This can't be undone)"
                            % self.game.directory,
                'title': "CONFIRM DANGEROUS OPERATION"
            })
            if dlg.result != Gtk.ResponseType.YES:
                return

        self.game.remove(remove_from_library, remove_contents)
        self.callback(self.game.slug, remove_from_library)

        self.on_close()
