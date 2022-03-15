from gettext import gettext as _

from lutris.config import LutrisConfig
from lutris.gui.config.common import GameDialogCommon


class RunnerConfigDialog(GameDialogCommon):
    """Runner config edit dialog."""

    def __init__(self, runner, parent=None):
        super().__init__(_("Configure %s") % runner.human_name, parent=parent)
        self.runner_name = runner.__class__.__name__
        self.saved = False
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name)
        self.build_notebook()
        self.build_tabs("runner")
        self.build_action_area(self.on_save)
        self.show_all()

    def on_save(self, wigdet, data=None):
        self.lutris_config.save()
        self.destroy()
