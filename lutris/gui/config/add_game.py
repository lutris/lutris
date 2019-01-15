from lutris.config import LutrisConfig, TEMP_CONFIG, make_game_config_id
from lutris.gui.widgets.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT


class AddGameDialog(Dialog, GameDialogCommon):
    """Add game dialog class."""

    def __init__(self, parent, game=None, runner=None, callback=None):
        super().__init__("Add a new game", parent=parent)
        self.game = game
        self.saved = False

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)
        if game:
            self.runner_name = game.runner_name
            self.slug = game.slug
        else:
            self.runner_name = runner
            self.slug = None

        self.game_config_id = self.get_config_id()
        self.lutris_config = LutrisConfig(
            runner_slug=self.runner_name,
            game_config_id=self.game_config_id,
            level="game",
        )
        self.build_notebook()
        self.build_tabs("game")
        self.build_action_area(self.on_save, callback)
        self.name_entry.grab_focus()
        self.connect("delete-event", self.on_cancel_clicked)
        self.show_all()

    def get_config_id(self):
        """For new games, create a special config type that won't be read
        from disk.
        """
        return make_game_config_id(self.slug) if self.slug else TEMP_CONFIG
