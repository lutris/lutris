from gettext import gettext as _

from lutris.config import LutrisConfig
from lutris.gui.config.common import GameDialogCommon
from lutris.runners import get_runner_human_name


class RunnerConfigDialog(GameDialogCommon):
    """Runner config edit dialog."""

    def __init__(self, runner, parent=None):
        super().__init__(_("Configure %s") % runner.human_name, config_level="runner", parent=parent)
        self.runner_name = runner.__class__.__name__
        self.saved = False
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name)
        self.build_notebook()
        self.build_tabs()
        self.show_all()

    def get_search_entry_placeholder(self):
        return _("Search %s options") % get_runner_human_name(self.runner_name)

    def on_save(self, wigdet, data=None):
        self.lutris_config.save()
        self.destroy()
