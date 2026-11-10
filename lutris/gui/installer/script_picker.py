from gi.repository import GObject, Gtk

from lutris.gui.installer.script_box import InstallerScriptBox


class InstallerPicker(Gtk.ListBox):
    """List box to pick between several installers"""

    __gsignals__ = {
        "installer-selected": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "selection-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, scripts, show_checkboxes=False):
        super().__init__()
        revealed = True
        # Each script is currently a separate DLC with its own single source; if a service
        # ever returns multiple sources for one DLC (grouped by "dlcid"), the checkbox rows
        # below would need to collapse those into one row with a source picker. TODO(#6063).
        for script in scripts:
            self.add(InstallerScriptBox(script, parent=self, revealed=revealed, show_checkbox=show_checkboxes))
            revealed = False  # Only reveal the first installer.
        self.connect("row-selected", self.on_activate)
        self.show_all()

    def get_selected_scripts(self):
        """Return the script dicts for all rows whose checkbox is ticked"""
        selected = []
        for row in self:
            script_box = row.get_children()[0]
            if script_box.get_selected():
                selected.append(script_box.script)
        return selected

    @staticmethod
    def on_activate(widget, row):
        """Handler for hiding and showing the revealers in children"""
        for script_box_row in widget:
            script_box = script_box_row.get_children()[0]
            script_box.reveal(False)
        installer_row = row.get_children()[0]
        installer_row.reveal()
