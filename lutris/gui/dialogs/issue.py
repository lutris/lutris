"""GUI dialog for reporting issues"""

import json
import os
from gettext import gettext as _

from gi.repository import Gio, GLib, Gtk

from lutris.gui.dialogs import NoticeDialog
from lutris.gui.widgets.window import BaseApplicationWindow
from lutris.util.linux import gather_system_info


class IssueReportWindow(BaseApplicationWindow):
    """Window for collecting and sending issue reports"""

    def __init__(self, application):
        super().__init__(application)

        self.title_label = Gtk.Label()
        self.vbox.append(self.title_label)

        title_label = Gtk.Label()
        title_label.set_markup(_("<b>Submit an issue</b>"))
        self.vbox.append(title_label)
        self.vbox.append(Gtk.Separator())

        issue_entry_label = Gtk.Label(
            label=_(
                "Describe the problem you're having in the text box below. "
                "This information will be sent the Lutris team along with your system information. "
                "You can also save this information locally if you are offline."
            )
        )
        issue_entry_label.set_max_width_chars(80)
        issue_entry_label.set_property("wrap", True)
        self.vbox.append(issue_entry_label)

        self.textview = Gtk.TextView()
        self.textview.set_pixels_above_lines(12)
        self.textview.set_pixels_below_lines(12)
        self.textview.set_left_margin(12)
        self.textview.set_right_margin(12)
        self.textview.set_hexpand(True)
        self.textview.set_vexpand(True)
        self.vbox.append(self.textview)

        self.action_buttons = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        self.vbox.append(self.action_buttons)

        cancel_button = self.get_action_button(_("C_ancel"), handler=lambda *x: self.destroy())
        self.action_buttons.append(cancel_button)

        save_button = self.get_action_button(_("_Save"), handler=self.on_save)
        self.action_buttons.append(save_button)

    def get_issue_info(self):
        buffer = self.textview.get_buffer()
        return {
            "comment": buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True),
            "system": gather_system_info(),
        }

    def on_save(self, _button):
        """Signal handler for the save button"""
        save_dialog = Gtk.FileDialog()
        save_dialog.set_title(_("Select a location to save the issue"))

        def on_folder_selected(_dialog, async_result):
            try:
                gfile = _dialog.select_folder_finish(async_result)
            except GLib.Error:
                return
            target_path = gfile.get_path()
            if not target_path:
                return
            issue_path = os.path.join(target_path, "lutris-issue-report.json")
            issue_info = self.get_issue_info()
            with open(issue_path, "w", encoding="utf-8") as issue_file:
                json.dump(issue_info, issue_file, indent=2)
            NoticeDialog(_("Issue saved in %s") % issue_path)

        save_dialog.select_folder(self, None, on_folder_selected)
        self.destroy()
