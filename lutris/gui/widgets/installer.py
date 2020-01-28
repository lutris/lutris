"""Widgets for the installer window"""
import os
from gi.repository import Gtk, GObject, Pango
from lutris.util.strings import gtk_safe
from lutris.util.log import logger
from lutris.gui.widgets.download_progress import DownloadProgressBox
from lutris.gui.widgets.utils import get_icon
from lutris.installer.steam_installer import SteamInstaller


class InstallerLabel(Gtk.Label):
    """A label for installers"""
    def __init__(self, text):
        super().__init__()
        self.set_line_wrap(True)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_alignment(0, 0.5)
        self.set_markup(text)


class InstallerScriptBox(Gtk.VBox):
    """Box displaying the details of a script, with associated action buttons"""
    def __init__(self, script, parent=None, revealed=False):
        super().__init__()
        self.script = script
        self.parent = parent
        self.revealer = None
        self.set_margin_left(12)
        self.set_margin_right(12)
        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6)
        box.add(self.get_icon())
        box.pack_start(self.get_infobox(), True, True, 0)
        box.add(self.get_install_button())
        self.add(box)
        self.add(self.get_revealer(revealed))

    def get_rating(self):
        """Return a string representation of the API rating"""
        try:
            rating = int(self.script["rating"])
        except (ValueError, TypeError, KeyError):
            return ""
        return "⭐" * rating

    def get_infobox(self):
        """Return the central information box"""
        info_box = Gtk.VBox(spacing=6)
        title_box = Gtk.HBox(spacing=6)
        title_box.add(InstallerLabel("<b>%s</b>" % gtk_safe(self.script["version"])))
        title_box.pack_start(InstallerLabel(""), True, True, 0)
        rating_label = InstallerLabel(self.get_rating())
        rating_label.set_alignment(1, 0.5)
        title_box.pack_end(rating_label, False, False, 0)
        info_box.add(title_box)
        info_box.add(InstallerLabel(gtk_safe(self.script["description"])))
        return info_box

    def get_revealer(self, revealed):
        """Return the revelaer widget"""
        self.revealer = Gtk.Revealer()
        self.revealer.add(self.get_notes())
        self.revealer.set_reveal_child(revealed)
        return self.revealer

    def get_icon(self):
        """Return the runner icon widget"""
        icon = get_icon(self.script["runner"], size=(32, 32))
        return icon

    def get_install_button(self):
        """Return the install button widget"""
        align = Gtk.Alignment()
        align.set(0, 0, 0, 0)

        install_button = Gtk.Button("Install")
        install_button.connect("clicked", self.on_install_clicked)
        align.add(install_button)
        return align

    def get_notes(self):
        """Return the notes widget"""
        notes = self.script["notes"].strip()
        if not notes:
            return Gtk.Alignment()
        notes_label = InstallerLabel(gtk_safe(notes))
        notes_label.set_margin_top(12)
        notes_label.set_margin_bottom(12)
        notes_label.set_margin_right(12)
        notes_label.set_margin_left(12)
        return notes_label

    def reveal(self, reveal=True):
        """Show or hide the information in the revealer"""
        if self.revealer:
            self.revealer.set_reveal_child(reveal)

    def on_install_clicked(self, _widget):
        """Handler to notify the parent of the selected installer"""
        self.parent.emit("installer-selected", self.script["slug"])


class InstallerPicker(Gtk.ListBox):
    """List box to pick between several installers"""

    __gsignals__ = {
        "installer-selected": (GObject.SIGNAL_RUN_FIRST, None, (str, ))
    }

    def __init__(self, scripts):
        super().__init__()
        revealed = True
        for script in scripts:
            self.add(InstallerScriptBox(script, parent=self, revealed=revealed))
            revealed = False  # Only reveal the first installer.
        self.connect('row-selected', self.on_activate)
        self.show_all()

    @staticmethod
    def on_activate(widget, row):
        """Handler for hiding and showing the revealers in children"""
        for script_box_row in widget:
            script_box = script_box_row.get_children()[0]
            script_box.reveal(False)
        installer_row = row.get_children()[0]
        installer_row.reveal()


class InstallerFileBox(Gtk.VBox):
    """Container for an installer file downloader / selector"""

    __gsignals__ = {
        "file-available": (GObject.SIGNAL_RUN_FIRST, None, (str, ))
    }

    def __init__(self, installer_file):
        super().__init__()
        self.installer_file = installer_file
        self.start_func = None
        self.abort_func = None
        self.state_label = None  # Use this label to display status update
        self.set_margin_left(12)
        self.set_margin_right(12)
        box = Gtk.Box(
            spacing=12,
            margin_top=6,
            margin_bottom=6,
        )
        provider = self.get_provider()
        file_provider_widget = self.get_file_provider_widget(provider)
        box.add(file_provider_widget)
        self.add(box)

    def get_file_provider_widget(self, provider):
        """Return the widget used to track progress of file"""
        if provider == "download":
            download_progress = DownloadProgressBox({
                "url": self.installer_file.url,
                "dest": self.installer_file.dest_file,
                "referer": self.installer_file.referer
            }, cancelable=True)
            download_progress.cancel_button.hide()
            download_progress.connect("complete", self.on_download_complete)
            download_progress.show()
            if (
                    not self.installer_file.uses_pga_cache()
                    and os.path.exists(self.installer_file.dest_file)
            ):
                os.remove(self.installer_file.dest_file)
            self.start_func = download_progress.start
            self.abort_func = download_progress.cancel

            return download_progress
        if provider == "pga":
            pga_label = Gtk.Label()
            pga_label.set_markup("URL: <b>%s</b>\nCached in: <b>%s</b>" % (
                gtk_safe(self.installer_file.url),
                gtk_safe(self.installer_file.dest_file)
            ))
            return pga_label
        if provider == "user":
            user_label = Gtk.Label()
            user_label.set_markup(self.get_user_message())
            return user_label
        if provider == "steam":
            steam_installer = SteamInstaller(self.installer_file.url,
                                             self.installer_file.id)
            steam_installer.connect("game-installed", self.on_download_complete)
            steam_installer.connect("state-changed", self.on_state_changed)
            self.start_func = steam_installer.install_steam_game
            self.stop_func = steam_installer.stop_func

            steam_box = Gtk.HBox(spacing=6)
            icon = get_icon("steam", size=(32, 32))
            icon.set_margin_right(6)
            steam_box.add(icon)
            info_box = Gtk.VBox(spacing=6)
            steam_label = InstallerLabel("Steam game for %s (appid: <b>%s</b>)" % (
                steam_installer.platform,
                steam_installer.appid
            ))
            info_box.add(steam_label)
            self.state_label = InstallerLabel("")
            info_box.add(self.state_label)
            steam_box.add(info_box)
            return steam_box

        return Gtk.Label(self.installer_file.url)

    def on_state_changed(self, _widget, state):
        """Update the state label with a new state"""
        self.state_label.set_text(state)

    def get_provider(self):
        """Return file provider used"""
        if self.installer_file.url.startswith(("$WINESTEAM", "$STEAM")):
            return "steam"
        if self.installer_file.url.startswith("N/A"):
            return "user"
        if self.installer_file.is_cached:
            return "pga"
        return "download"

    def get_user_message(self):
        """Return the message prompting to provide a file"""
        if self.installer_file.url.startswith("N/A"):
            # Ask the user where the file is located
            parts = self.installer_file.url.split(":", 1)
            if len(parts) == 2:
                return parts[1]
            return "Please select file '%s'" % self.installer_file.id

    def start(self):
        """Starts the download of the file"""
        provider = self.get_provider()
        self.installer_file.prepare()
        if provider == "pga":
            logger.info("File is cached!")
            self.emit("file-available", self.installer_file.id)
            return
        if self.start_func:
            logger.info("Start func: %s", self.start_func)
            self.start_func()

    def on_download_cancelled(self):
        """Handle cancellation of installers"""

    def on_download_complete(self, widget, _data=None):
        """Action called on a completed download."""
        if isinstance(widget, SteamInstaller):
            self.installer_file.dest_file = widget.get_steam_data_path()
        self.emit("file-available", self.installer_file.id)


class InstallerFilesBox(Gtk.ListBox):
    """List box presenting all files needed for an installer"""

    __gsignals__ = {
        "files-available": (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self, installer_files, parent):
        super().__init__()
        self.parent = parent
        self.installer_files = installer_files
        self.available_files = set()
        self.installer_files_boxes = {}
        for installer_file in installer_files:
            installer_file_box = InstallerFileBox(installer_file)
            installer_file_box.connect("file-available", self.on_file_available)
            self.installer_files_boxes[installer_file.id] = installer_file_box
            self.add(installer_file_box)
        self.show_all()

    def start_all(self):
        """Start all downloads"""
        for file_id in self.installer_files_boxes:
            self.installer_files_boxes[file_id].start()

    def on_file_available(self, _widget, file_id):
        """A new file is available"""
        self.available_files.add(file_id)
        if len(self.available_files) == len(self.installer_files):
            logger.info("All files ready")
            self.emit("files-available")

    def get_game_files(self):
        """Return a mapping of the local files usable by the interpreter"""
        return {
            installer_file.id: installer_file.dest_file
            for installer_file in self.installer_files
        }
