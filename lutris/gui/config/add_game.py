from lutris.config import LutrisConfig, make_game_config_id
from lutris.gui.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT
from lutris.util.log import logger


class AddGameDialog(Dialog, GameDialogCommon):
    """Add game dialog class."""

    def __init__(self, parent, game=None, runner=None):
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

        self.lutris_config = LutrisConfig(
            runner_slug=self.runner_name,
            game_config_id=self.get_config_id(),
            level="game",
        )
        self.build_notebook()
        self.build_tabs("game")
        self.build_action_area(self.on_save)
        self.name_entry.grab_focus()
        self.connect("delete-event", self.on_cancel_clicked)
        self.show_all()

    def get_config_id(self):
        """For new games, create a special config type that won't be read
        from disk.
        """
        if not self.slug:
            logger.error("Stop calling get_config_id when no slug is set")
            return
        return make_game_config_id(self.slug)
