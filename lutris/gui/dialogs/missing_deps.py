"""Dialog for detecting and installing missing Wine/DXVK system dependencies."""

import os
import subprocess
from gettext import gettext as _
from typing import Optional

from gi.repository import GLib, Gtk

from lutris import settings
from lutris.util.downloader import SimpleDownloader
from lutris.util.extract import extract_archive
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class MissingWineDepsDialog(Gtk.Dialog):
    """Informs the user of missing system packages required for Wine games,
    offers to install them inline with a password prompt, and reports the result.

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
        install_cmd = " ".join(["sudo"] + self.dep_info["install_command"])

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

        # Password entry
        pw_label = Gtk.Label(label=_("Enter your sudo password to install now:"), visible=True)
        pw_label.set_xalign(0)
        content.pack_start(pw_label, False, False, 0)

        self._password_entry = Gtk.Entry(visible=True)
        self._password_entry.set_visibility(False)
        self._password_entry.set_placeholder_text(_("Password"))
        self._password_entry.set_activates_default(True)
        content.pack_start(self._password_entry, False, False, 0)

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

        password = self._password_entry.get_text()
        if not password:
            self._status_label.set_markup(_("<span foreground='red'>Please enter your password.</span>"))
            # Stop dialog from closing
            GLib.idle_add(lambda: self.run())
            return

        self._start_install(password)

    def _start_install(self, password: str) -> None:
        self._install_button.set_sensitive(False)
        self._password_entry.set_sensitive(False)
        self._progress.set_visible(True)
        self._status_label.set_markup(_("<i>Installing packages…</i>"))

        self._pulse_timer = GLib.timeout_add(100, self._pulse_progress)

        self._install_call = AsyncCall(
            self._run_install,
            self._on_install_complete,
            password,
        )
        self._install_call.start()

    def _pulse_progress(self) -> bool:
        self._progress.pulse()
        return True

    def _run_install(self, password: str) -> tuple[bool, str]:
        """Run the install command with sudo -S (reads password from stdin).
        Returns (success, output_message).
        """
        cmd = ["sudo", "-S"] + self.dep_info["install_command"]
        try:
            result = subprocess.run(
                cmd,
                input=(password + "\n").encode(),
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0:
                return True, _("Packages installed successfully.")
            stderr = result.stderr.decode(errors="replace").strip()
            if "incorrect password" in stderr.lower() or (result.returncode == 1 and not stderr):
                return False, _("Incorrect password. Please try again.")
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
            self._password_entry.set_sensitive(True)
            return

        success, message = result
        self.install_succeeded = success

        if success:
            self._status_label.set_markup(_("<span foreground='green'>✓ %s</span>") % message)
            # Auto-close after a short delay so user can see the success message
            GLib.timeout_add(1500, self.destroy)
        else:
            self._status_label.set_markup(_("<span foreground='red'>%s</span>") % message)
            self._install_button.set_sensitive(True)
            self._password_entry.set_sensitive(True)
            self._password_entry.set_text("")
            self._password_entry.grab_focus()

    def run_and_wait(self) -> bool:
        """Show the dialog and block until it is dismissed.
        Returns True if packages were successfully installed, False otherwise.
        """
        self.run()
        return self.install_succeeded


class MissingWineRunnerDialog(Gtk.Dialog):
    """Informs the user that Wine Staging is not installed and offers to
    download and install it automatically from Kron4ek's Wine-Builds releases.

    Usage:
        dialog = MissingWineRunnerDialog(runner_info, parent=window)
        dialog.run_and_wait()  # blocks until install completes or user skips
    """

    def __init__(self, runner_info: dict, parent: Optional[Gtk.Window] = None):
        super().__init__(
            title=_("Wine Staging Not Installed"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.runner_info = runner_info
        self.install_succeeded = False
        self._downloader: Optional[SimpleDownloader] = None

        self.set_border_width(16)
        self.set_default_size(520, -1)

        self._build_ui()
        self.show_all()

    def _build_ui(self) -> None:
        content = self.get_content_area()
        content.set_spacing(12)

        version = self.runner_info["version"]

        header = Gtk.Label(visible=True)
        header.set_markup(
            _(
                "<b>Wine Staging is recommended for Windows games</b>\n"
                "Wine Staging includes patches that improve compatibility and performance, "
                "and is required for some games (such as Battle.net) to run at all."
            )
        )
        header.set_line_wrap(True)
        header.set_xalign(0)
        content.pack_start(header, False, False, 0)

        ver_label = Gtk.Label(label=_("Latest available: %s") % version, visible=True)
        ver_label.set_xalign(0)
        content.pack_start(ver_label, False, False, 0)

        note = Gtk.Label(
            label=_("After installing, open the Runner Manager to select Wine Staging for this game."),
            visible=True,
        )
        note.set_line_wrap(True)
        note.set_xalign(0)
        content.pack_start(note, False, False, 0)

        self._status_label = Gtk.Label(label="", visible=True)
        self._status_label.set_xalign(0)
        self._status_label.set_line_wrap(True)
        content.pack_start(self._status_label, False, False, 0)

        self._progress = Gtk.ProgressBar(visible=False)
        self._progress.set_pulse_step(0.05)
        content.pack_start(self._progress, False, False, 0)

        self.add_button(_("Skip"), Gtk.ResponseType.CANCEL)
        self._install_button = self.add_button(_("Install Wine Staging"), Gtk.ResponseType.OK)
        self._install_button.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        self.connect("response", self._on_response)

    def _on_response(self, _dialog, response: Gtk.ResponseType) -> None:
        if response != Gtk.ResponseType.OK:
            self.destroy()
            return
        self._start_download()

    def _start_download(self) -> None:
        url = self.runner_info["url"]
        dest = os.path.join(settings.CACHE_DIR, os.path.basename(url))

        self._install_button.set_sensitive(False)
        self._progress.set_visible(True)
        self._status_label.set_markup(_("<i>Downloading Wine Staging…</i>"))

        self._downloader = SimpleDownloader(url, dest, overwrite=True)
        self._downloader.start()
        GLib.timeout_add(200, self._check_download_progress)

    def _check_download_progress(self) -> bool:
        dl = self._downloader
        if dl is None:
            return False
        if dl.state == dl.CANCELLED:
            self._on_download_error("Download cancelled")
            return False
        if dl.state == dl.ERROR:
            self._on_download_error(str(dl.error))
            return False
        dl.check_progress()
        pct = dl.progress_percentage
        if pct and pct >= 1:
            self._progress.set_fraction(pct / 100)
            self._progress.set_text(_("%.0f%%") % pct)
            self._progress.set_show_text(True)
        else:
            self._progress.pulse()
        if dl.state == dl.COMPLETED:
            self._status_label.set_markup(_("<i>Extracting…</i>"))
            self._progress.set_fraction(1.0)
            src = dl.dest
            dst = os.path.join(self.runner_info["runner_dir"], self.runner_info["version"])
            AsyncCall(self._extract, self._on_extract_complete, src, dst)
            return False
        return True

    def _extract(self, src: str, dst: str) -> tuple[bool, str]:
        try:
            os.makedirs(dst, exist_ok=True)
            extract_archive(src, dst)
            os.remove(src)
            return True, ""
        except Exception as ex:  # pylint: disable=broad-except
            return False, str(ex)

    def _on_extract_complete(self, result: tuple[bool, str], error) -> None:
        self._progress.set_visible(False)
        if error or not result[0]:
            msg = str(error) if error else result[1]
            self._on_download_error(msg)
            return
        self.install_succeeded = True
        self._status_label.set_markup(
            _("<span foreground='green'>✓ Wine Staging installed. Select it in the Runner Manager.</span>")
        )
        GLib.timeout_add(2000, self.destroy)

    def _on_download_error(self, message: str) -> None:
        self._progress.set_visible(False)
        self._status_label.set_markup(_("<span foreground='red'>Failed: %s</span>") % GLib.markup_escape_text(message))
        self._install_button.set_sensitive(True)

    def run_and_wait(self) -> bool:
        """Show the dialog and block until it is dismissed.
        Returns True if Wine Staging was successfully installed, False otherwise.
        """
        self.run()
        return self.install_succeeded
