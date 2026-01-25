from gettext import gettext as _

from lutris.gui.config.game_common import GameDialogCommon


class EditGameConfigDialog(GameDialogCommon):
    """Game config edit dialog."""

    def __init__(self, parent, game):
        super().__init__(_("Configure %s") % game.name, config_level="game", parent=parent)
        self.game = game
        self.lutris_config = game.config
        self.runner_name = game.runner_name
        self.build_notebook()
        self.build_tabs()
        self.show_all()
