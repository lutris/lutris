from gi.repository import GObject, Gtk

from lutris.gui.installer.script_box import InstallerScriptBox


class InstallerPicker(Gtk.ListBox):
    """List box to pick between several installers"""

    __gsignals__ = {"installer-selected": (GObject.SIGNAL_RUN_FIRST, None, (str,))}

    def __init__(self, scripts):
        super().__init__()
        revealed = True
        for script in scripts:
            self.append(InstallerScriptBox(script, parent=self, revealed=revealed))
            revealed = False  # Only reveal the first installer.
        self.connect("row-selected", self.on_activate)

    @staticmethod
    def on_activate(widget, row):
        """Handler for hiding and showing the revealers in children"""
        for script_box_row in widget:
            script_box = script_box_row.get_child()
            script_box.reveal(False)
        installer_row = row.get_child()
        installer_row.reveal()
