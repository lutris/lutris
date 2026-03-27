"""Dialog for managing user profiles in Lutris."""

import os
import shutil
from gettext import gettext as _
from typing import Optional, cast

from gi.repository import Gtk

from lutris.database.profiles import DEFAULT_PROFILE_ID, delete_profile, update_profile
from lutris.gui.dialogs import Dialog
from lutris.profile import get_profile_manager
from lutris.util import strings
from lutris.util.log import logger


def _get_profile_disk_usage(profile_dir: str) -> int:
    """Return total bytes used under *profile_dir*."""
    total = 0
    if not os.path.isdir(profile_dir):
        return 0
    for root, _dirs, files in os.walk(profile_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


class ProfileDialog(Dialog):
    """Modal dialog that lets the user create, rename, switch and delete profiles."""

    def __init__(self, parent: Gtk.Widget = None):
        super().__init__(
            title=_("Manage Profiles"),
            parent=parent,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        )
        self.set_default_size(480, 360)
        self.pm = get_profile_manager()

        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        # ---- Profile list ----
        list_label = Gtk.Label(label=_("Profiles"))
        list_label.set_halign(Gtk.Align.START)
        content.pack_start(list_label, False, False, 0)

        self.store = Gtk.ListStore(str, str, str)  # id, display name, disk usage
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(True)

        col_name = Gtk.TreeViewColumn(_("Name"), Gtk.CellRendererText(), text=1)
        col_name.set_expand(True)
        self.tree.append_column(col_name)

        col_size = Gtk.TreeViewColumn(_("Disk usage"), Gtk.CellRendererText(), text=2)
        self.tree.append_column(col_size)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(160)
        scroll.add(self.tree)
        content.pack_start(scroll, True, True, 0)

        # ---- Action buttons row ----
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.btn_switch = Gtk.Button(label=_("Switch to"))
        self.btn_switch.connect("clicked", self.on_switch_clicked)
        btn_box.pack_start(self.btn_switch, False, False, 0)

        self.btn_rename = Gtk.Button(label=_("Rename…"))
        self.btn_rename.connect("clicked", self.on_rename_clicked)
        btn_box.pack_start(self.btn_rename, False, False, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.connect("clicked", self.on_delete_clicked)
        btn_box.pack_end(self.btn_delete, False, False, 0)

        content.pack_start(btn_box, False, False, 0)

        # ---- New profile section ----
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        content.pack_start(sep, False, False, 4)

        new_label = Gtk.Label(label=_("Create new profile"))
        new_label.set_halign(Gtk.Align.START)
        content.pack_start(new_label, False, False, 0)

        new_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.new_name_entry = Gtk.Entry()
        self.new_name_entry.set_placeholder_text(_("Profile name"))
        self.new_name_entry.set_activates_default(True)
        new_row.pack_start(self.new_name_entry, True, True, 0)

        btn_create = Gtk.Button(label=_("Create"))
        btn_create.connect("clicked", self.on_create_clicked)
        new_row.pack_start(btn_create, False, False, 0)
        content.pack_start(new_row, False, False, 0)

        self.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        self.set_default_response(Gtk.ResponseType.CLOSE)

        self.refresh_list()
        self.show_all()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def refresh_list(self) -> None:
        self.store.clear()
        active = self.pm.current_profile_id
        for profile in self.pm.get_all_profiles():
            pid = profile["id"]
            display_name = profile["name"]
            if pid == active:
                display_name += _(" (active)")
            profile_dir = self.pm.get_profile_dir(pid)
            usage = strings.human_size(_get_profile_disk_usage(profile_dir))
            self.store.append([pid, display_name, usage])

    def _get_selected_id(self) -> Optional[str]:
        selection = self.tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return None
        return model[tree_iter][0]

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_switch_clicked(self, _btn) -> None:
        pid = self._get_selected_id()
        if not pid:
            return
        try:
            self.pm.switch(pid)
            self.refresh_list()
        except Exception as ex:
            logger.error("Failed to switch profile: %s", ex)

    def on_rename_clicked(self, _btn) -> None:
        pid = self._get_selected_id()
        if not pid:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_("Rename profile"),
        )
        dialog.set_modal(True)
        dialog.format_secondary_text(_("Enter a new name for the profile:"))
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        cast(Gtk.Box, dialog.get_message_area()).pack_start(entry, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and new_name:
            update_profile(pid, name=new_name)
            self.refresh_list()

    def on_delete_clicked(self, _btn) -> None:
        pid = self._get_selected_id()
        if not pid or pid == DEFAULT_PROFILE_ID:
            return
        confirm = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Delete profile?"),
        )
        confirm.set_modal(True)
        confirm.format_secondary_text(
            _(
                "This will permanently delete all Wine prefixes and saves stored "
                "under this profile. The game installations themselves are not affected."
            )
        )
        response = confirm.run()
        confirm.destroy()
        if response != Gtk.ResponseType.YES:
            return
        # Remove profile directory
        profile_dir = self.pm.get_profile_dir(pid)
        if os.path.isdir(profile_dir):
            try:
                shutil.rmtree(profile_dir)
            except OSError as ex:
                logger.error("Could not remove profile directory %s: %s", profile_dir, ex)
        # Remove DB records
        try:
            delete_profile(pid)
        except ValueError as ex:
            logger.error("Could not delete profile: %s", ex)
        # If we deleted the active profile, fall back to default
        if self.pm.current_profile_id == pid:
            self.pm.switch(DEFAULT_PROFILE_ID)
        self.refresh_list()

    def on_create_clicked(self, _btn) -> None:
        name = self.new_name_entry.get_text().strip()
        if not name:
            return
        self.pm.create_profile(name)
        self.new_name_entry.set_text("")
        self.refresh_list()
