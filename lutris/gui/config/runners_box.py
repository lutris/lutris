"""Add, remove and configure runners"""
from gi.repository import Gtk

from lutris import runners, settings
from lutris.gui.config.runner_box import RunnerBox
from lutris.gui.widgets.utils import open_uri


class RunnersBox(Gtk.VBox):
    """List of all available runners"""

    def __init__(self):
        super().__init__(visible=True)
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_right(80)
        self.set_margin_left(80)

        self.runner_listbox = Gtk.ListBox(visible=True)
        self.add(self.runner_listbox)
        for runner_name in sorted(runners.__all__):
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(RunnerBox(runner_name))
            self.runner_listbox.add(list_box_row)

    @staticmethod
    def on_folder_clicked(_widget):
        open_uri("file://" + settings.RUNNER_DIR)
