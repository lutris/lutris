from lutris.gui.widgets.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT


class EditGameConfigDialog(Dialog, GameDialogCommon):
    """Game config edit dialog."""

    def __init__(self, parent, game, callback):
        super().__init__("Configure %s" % game.name, parent=parent)
        self.game = game
        self.lutris_config = game.config
        self.game_config_id = game.config.game_config_id
        self.slug = game.slug
        self.runner_name = game.runner_name

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs("game")
        self.build_action_area(self.on_save, callback)
        self.connect("delete-event", self.on_cancel_clicked)
        self.show_all()
