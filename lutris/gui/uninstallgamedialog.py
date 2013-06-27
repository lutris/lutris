from lutris.gui.dialogs import GtkBuilderDialog
from lutris import pga


class UninstallGameDialog(GtkBuilderDialog):
    glade_file = 'dialog-uninstall-game.ui'
    dialog_object = 'uninstall-game-dialog'

    def initialize(self, game=None):
        game_info = pga.get_game_by_slug(game)
        print game_info

        cancel_button = self.builder.get_object('cancel_button')
        cancel_button.connect('clicked', self.on_close)

        apply_button = self.builder.get_object('apply_button')
        apply_button.connect('clicked', self.on_apply_button_clicked)

    def on_apply_button_clicked(self, widget):
        widget.set_sensitive(False)
