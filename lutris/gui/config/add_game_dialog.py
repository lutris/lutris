from gettext import gettext as _

from lutris.config import LutrisConfig
from lutris.gui.config.game_common import GameDialogCommon


class AddGameDialog(GameDialogCommon):
    """Add game dialog class."""

    def __init__(self, parent, game=None, runner=None):
        super().__init__(_("Add a new game"), config_level="game", parent=parent)
        self.game = game
        self.saved = False
        if game:
            self.runner_name = game.runner_name
            self.slug = game.slug
        else:
            self.runner_name = runner
            self.slug = None

        self.lutris_config = LutrisConfig(
            runner_slug=self.runner_name,
            level="game",
        )
        self.build_notebook()
        self.build_tabs()
        self.name_entry.grab_focus()
        self.show_all()
