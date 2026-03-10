from gettext import gettext as _

from lutris.config import LutrisConfig
from lutris.gui.config.game_common import GameDialogCommon


class AddGameDialog(GameDialogCommon):
    """Add game dialog class."""

    def __init__(self, parent, game=None, runner=None):
        super().__init__(_("Add a new game"), config_level="game", parent=parent)
        self.game = game
        self.saved = False

        self.lutris_config = LutrisConfig(
            runner_slug=game.runner_name if game else runner,
            level="game",
        )
        self.build_notebook()
        self.build_tabs()
        self.info_box.grab_focus()
        self.show_all()
