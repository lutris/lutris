from lutris.config import LutrisConfig
from lutris.gui.widgets.dialogs import Dialog
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config_boxes import SystemBox
from lutris.gui.config import DIALOG_WIDTH, DIALOG_HEIGHT


class SystemConfigDialog(Dialog, GameDialogCommon):
    def __init__(self, parent=None):
        super().__init__("System preferences", parent=parent)

        self.game = None
        self.runner_name = None
        self.lutris_config = LutrisConfig()

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.system_box = SystemBox(self.lutris_config)
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.vbox.pack_start(self.system_sw, True, True, 0)
        self.build_action_area(self.on_save)
        self.show_all()

    def on_save(self, widget):
        self.lutris_config.save()
        self.destroy()
