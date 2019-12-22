from lutris.config import LutrisConfig
from lutris.gui.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT


class SystemConfigDialog(Dialog, GameDialogCommon):
    def __init__(self, parent=None):
        super().__init__("System preferences", parent=parent)

        self.game = None
        self.runner_name = None
        self.lutris_config = LutrisConfig()

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_tabs("system")
        self.build_action_area(self.on_save)
        self.build_headerbar()
        self.viewswitcher.set_stack(self.stack)
        self.set_titlebar(self.header)
        self.show_all()

    def on_save(self, _widget):
        self.lutris_config.save()
        self.destroy()
