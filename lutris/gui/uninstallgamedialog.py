from gi.repository import Gtk
from lutris.gui.dialogs import GtkBuilderDialog
from lutris import pga
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

    def initialize(self, game=None, callback=None):
        self.game_slug = game
        game_info = pga.get_game_by_slug(game)
        self.callback = callback

        game_name = game_info['name']
        self.substitute_label(self.builder.get_object('description_label'),
                              'game', game_name)

        self.substitute_label(
            self.builder.get_object('remove_from_library_button'),
            'game', game_name
        )
        self.game_directory = game_info['directory']
        remove_contents_button = self.builder.get_object(
            'remove_contents_button'
        )
        if not is_removeable(self.game_directory):
            remove_contents_button.set_sensitive(False)
            self.game_directory = "disk"
        self.substitute_label(remove_contents_button, 'path',
                              self.game_directory)

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
                            % self.game_directory,
                'title': "CONFIRM DANGEROUS OPERATION"
            })
            if dlg.result != Gtk.ResponseType.YES:
                return

        game = Game(self.game_slug)
        game.remove(remove_from_library, remove_contents)
        self.callback(self.game_slug, remove_from_library)

        self.on_close()
