"""Add, remove and configure runners"""
from gettext import gettext as _

from gi.repository import GLib, Gtk

from lutris import runners, settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.runner_box import RunnerBox
from lutris.gui.widgets.utils import open_uri


class RunnersBox(BaseConfigBox):
    """List of all available runners"""

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Add, remove or configure runners")))
        self.add(self.get_description_label(
            _("Runners are programs such as emulators, engines or "
              "translation layers capable of running games.")
        ))
        self.runner_listbox = Gtk.ListBox(visible=True)
        self.pack_start(self.runner_listbox, False, False, 12)
        GLib.idle_add(self.populate_runners)

    def populate_runners(self):
        for runner_name in sorted(runners.__all__):
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(RunnerBox(runner_name))
            self.runner_listbox.add(list_box_row)

    @staticmethod
    def on_folder_clicked(_widget):
        open_uri("file://" + settings.RUNNER_DIR)
