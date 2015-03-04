from gi.repository import Gtk
from lutris.gui.dialogs import GtkBuilderDialog
from lutris.game import Game
from lutris.util.system import is_removeable
from lutris.gui.dialogs import QuestionDialog
from lutris.runners import InvalidRunner


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

        replacement = replacement.replace('&', '&amp;')
        set_text(get_text().replace("{%s}" % name, replacement))

    def initialize(self, slug=None, callback=None):
        self.game = Game(slug)
        self.callback = callback
        runner = self.game.runner

        self.substitute_label(self.builder.get_object('description_label'),
                              'game', self.game.name)

        self.substitute_label(
            self.builder.get_object('remove_from_library_button'),
            'game', self.game.name
        )
        remove_contents_button = self.builder.get_object(
            'remove_contents_button'
        )
        if self.game.is_installed:
            if hasattr(runner, 'own_game_remove_method'):
                remove_contents_button.set_label(runner.own_game_remove_method)
            else:
                try:
                    default_path = runner.default_path
                except AttributeError:
                    default_path = "/"
                try:
                    game_path = runner.game_path
                except AttributeError:
                    game_path = '/'
                if not is_removeable(game_path, excludes=[default_path]):
                    remove_contents_button.set_sensitive(False)

            path = self.game.directory or 'disk'
            self.substitute_label(remove_contents_button, 'path', path)
            remove_contents_button.get_children()[0].set_use_markup(True)
        else:
            remove_contents_button.hide()

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
        if remove_contents and not hasattr(self.game.runner,
                                           'no_game_remove_warning'):
            game_dir = self.game.directory.replace('&', '&amp;')
            dlg = QuestionDialog({
                'question': "Are you sure you want to delete EVERYTHING under "
                            "\n<b>%s</b>?\n (This can't be undone)"
                            % game_dir,
                'title': "CONFIRM DANGEROUS OPERATION"
            })
            if dlg.result != Gtk.ResponseType.YES:
                widget.set_sensitive(True)
                return

        self.game.remove(remove_from_library, remove_contents)
        self.callback(self.game.slug, remove_from_library)

        self.on_close()
