from gettext import gettext as _

from lutris.config import LutrisConfig
from lutris.gui.config.game_common import GameDialogCommon


class EditGameConfigDialog(GameDialogCommon):
    """Game config edit dialog."""

    def __init__(self, parent, game):
        super().__init__(_("Configure %s") % game.name, config_level="game", parent=parent)
        self.game = game
        # Read the saved file for each new dialog without replacing an active runner.
        self.lutris_config = LutrisConfig(runner_slug=game.runner_name, game_config_id=game.game_config_id)
        self.runner_name = game.runner_name
        self.build_notebook()
        self.build_tabs()
        self.show_all()
