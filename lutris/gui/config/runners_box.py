"""Add, remove and configure runners"""

from gettext import gettext as _

from gi.repository import Gtk

from lutris import runners, settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.runner_box import RunnerBox
from lutris.gui.widgets.utils import open_uri
from lutris.search import RunnerSearch


class RunnersBox(BaseConfigBox):
    """List of all available runners"""

    def __init__(self):
        super().__init__()
        self._runner_search = RunnerSearch("")
        self.search_entry_placeholder_text = ""

        self.add(self.get_section_label(_("Add, remove or configure runners")))
        self.add(
            self.get_description_label(
                _("Runners are programs such as emulators, engines or translation layers capable of running games.")
            )
        )
        self.search_failed_label = Gtk.Label(_("No runners matched the search"))
        self.pack_start(self.search_failed_label, False, False, 0)
        self.runner_list_frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.runner_listbox = Gtk.ListBox(visible=True)
        self.runner_list_frame.add(self.runner_listbox)
        self.pack_start(self.runner_list_frame, False, False, 0)

    def populate_runners(self):
        runner_count = 0
        for runner_name in sorted(runners.__all__):
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(RunnerBox(runner_name))
            self.runner_listbox.add(list_box_row)
            runner_count += 1

        self._update_row_visibility()
        # pretty sure there will always be many runners, so assume plural
        self.search_entry_placeholder_text = _("Search %s runners") % runner_count

    @staticmethod
    def on_folder_clicked(_widget):
        open_uri("file://" + settings.RUNNER_DIR)

    @property
    def filter(self):
        return self._runner_search.text

    @filter.setter
    def filter(self, value):
        self._runner_search = RunnerSearch(value)
        self._update_row_visibility()

    def _update_row_visibility(self):
        search = self._runner_search

        any_matches = False
        for row in self.runner_listbox.get_children():
            runner_box = row.get_child()
            runner = runner_box.runner
            match = search.matches(runner)
            row.set_visible(match)
            if match:
                any_matches = True

        self.runner_list_frame.set_visible(any_matches)
        self.search_failed_label.set_visible(not any_matches)
