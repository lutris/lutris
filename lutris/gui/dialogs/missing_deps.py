"""Dialog for detecting and installing missing Wine/DXVK system dependencies."""

import shutil
import subprocess
from gettext import gettext as _
from typing import Optional

from gi.repository import GLib, Gtk

from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class MissingWineDepsDialog(Gtk.Dialog):
    """Informs the user of missing system packages required for Wine games,
    offers to install them via pkexec, and reports the result.

    Usage:
        dialog = MissingWineDepsDialog(dep_info, parent=window)
        dialog.run_and_wait()  # blocks until install completes or user cancels
    """

    def __init__(self, dep_info: dict, parent: Optional[Gtk.Window] = None):
        super().__init__(
            title=_("Missing System Dependencies"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.dep_info = dep_info
        self.install_succeeded = False
        self._install_call: Optional[AsyncCall] = None

        self.set_border_width(16)
        self.set_default_size(520, -1)

        self._build_ui()
        self.show_all()

    def _build_ui(self) -> None:
        content = self.get_content_area()
        content.set_spacing(12)

        gpu = self.dep_info["gpu_vendor"].upper()
        missing = self.dep_info["missing"]
        install_cmd = " ".join(["pkexec"] + self.dep_info["install_command"])

        # Header
        header = Gtk.Label(visible=True)
        header.set_markup(
            _(
                "<b>Missing packages detected for your %s GPU</b>\n"
                "The following system packages are required for Wine and DXVK to work correctly:"
            )
            % gpu
        )
        header.set_line_wrap(True)
        header.set_xalign(0)
        content.pack_start(header, False, False, 0)

        # Package list
        pkg_text = "\n".join("  • " + p for p in missing)
        pkg_label = Gtk.Label(label=pkg_text, visible=True)
        pkg_label.set_xalign(0)
        pkg_label.set_selectable(True)
        content.pack_start(pkg_label, False, False, 0)

        # Command preview
        cmd_label = Gtk.Label(visible=True)
        cmd_label.set_markup(_("<b>Install command:</b>"))
        cmd_label.set_xalign(0)
        content.pack_start(cmd_label, False, False, 0)

        cmd_box = Gtk.Entry(visible=True, editable=False, text=install_cmd)
        cmd_box.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-copy-symbolic")
        cmd_box.connect("icon-press", self._on_copy_command)
        content.pack_start(cmd_box, False, False, 0)

        # Status label (shown during/after install)
        self._status_label = Gtk.Label(label="", visible=True)
        self._status_label.set_xalign(0)
        self._status_label.set_line_wrap(True)
        content.pack_start(self._status_label, False, False, 0)

        # Progress bar (hidden until install starts)
        self._progress = Gtk.ProgressBar(visible=False)
        self._progress.set_pulse_step(0.1)
        content.pack_start(self._progress, False, False, 0)

        # Buttons
        self.add_button(_("Skip"), Gtk.ResponseType.CANCEL)
        self._install_button = self.add_button(_("Install"), Gtk.ResponseType.OK)
        self._install_button.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        self.connect("response", self._on_response)

    def _on_copy_command(self, entry: Gtk.Entry, icon_pos, event) -> None:
        entry.select_region(0, -1)
        entry.copy_clipboard()

    def _on_response(self, _dialog, response: Gtk.ResponseType) -> None:
        if response != Gtk.ResponseType.OK:
            self.destroy()
            return

        self._start_install()

    def _start_install(self) -> None:
        self._install_button.set_sensitive(False)
        self._progress.set_visible(True)
        self._status_label.set_markup(_("<i>Installing packages…</i>"))

        self._pulse_timer = GLib.timeout_add(100, self._pulse_progress)

        self._install_call = AsyncCall(
            self._run_install,
            self._on_install_complete,
        )
        self._install_call.start()

    def _pulse_progress(self) -> bool:
        self._progress.pulse()
        return True

    def _run_install(self) -> tuple[bool, str]:
        """Run the install command via pkexec, which handles authentication natively.
        Returns (success, output_message).
        """
        if not shutil.which("pkexec"):
            return False, _("pkexec not found. Run the install command manually.")

        cmd = ["pkexec"] + self.dep_info["install_command"]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                return True, _("Packages installed successfully.")
            if result.returncode == 126:
                return False, _("Authentication cancelled.")
            if result.returncode == 127:
                return False, _("Authentication failed.")
            stderr = result.stderr.decode(errors="replace").strip()
            return False, _("Install failed:\n") + stderr[-500:]
        except subprocess.TimeoutExpired:
            return False, _("Install timed out after 5 minutes.")
        except Exception as ex:  # pylint: disable=broad-except
            return False, _("Unexpected error: %s") % str(ex)

    def _on_install_complete(self, result: tuple[bool, str], error) -> None:
        if hasattr(self, "_pulse_timer"):
            GLib.source_remove(self._pulse_timer)

        self._progress.set_visible(False)

        if error:
            logger.error("Dependency install error: %s", error)
            self._status_label.set_markup(_("<span foreground='red'>An error occurred: %s</span>") % str(error))
            self._install_button.set_sensitive(True)
            return

        success, message = result
        self.install_succeeded = success

        if success:
            self._status_label.set_markup(_("<span foreground='green'>✓ %s</span>") % message)
            GLib.timeout_add(1500, self.destroy)
        else:
            self._status_label.set_markup(_("<span foreground='red'>%s</span>") % message)
            self._install_button.set_sensitive(True)

    def run_and_wait(self) -> bool:
        """Show the dialog and block until it is dismissed.
        Returns True if packages were successfully installed, False otherwise.
        """
        loop = GLib.MainLoop()
        self.connect("destroy", lambda _: loop.quit())
        loop.run()
        return self.install_succeeded
