from lutris.config import LutrisConfig
from lutris.gui.widgets.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT


class RunnerConfigDialog(Dialog, GameDialogCommon):
    """Runner config edit dialog."""

    def __init__(self, runner, parent=None):
        self.runner_name = runner.__class__.__name__
        super().__init__("Configure %s" % runner.human_name, parent=parent)

        self.game = None
        self.saved = False
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name)

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs("runner")
        self.build_action_area(self.on_save)
        self.show_all()

    def on_save(self, wigdet, data=None):
        self.lutris_config.save()
        self.destroy()
