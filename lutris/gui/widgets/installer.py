"""Widgets for the installer window"""
import os
import shutil
from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.widgets.download_progress import DownloadProgressBox
from lutris.installer.steam_installer import SteamInstaller
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import add_url_tags, gtk_safe


class InstallerLabel(Gtk.Label):

    """A label for installers"""
    def __init__(self, text, wrap=True):
        super().__init__()
        if wrap:
            self.set_line_wrap(True)
            self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        else:
            self.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        self.set_alignment(0, 0.5)
        self.set_margin_right(12)
        self.set_markup(text)
        self.props.can_focus = False
        self.set_tooltip_text(text)


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
        info_box.add(InstallerLabel(add_url_tags(self.script["description"])))
        return info_box

    def get_revealer(self, revealed):
        """Return the revelaer widget"""
        self.revealer = Gtk.Revealer()
        self.revealer.add(self.get_notes())
        self.revealer.set_reveal_child(revealed)
        return self.revealer

    def get_install_button(self):
        """Return the install button widget"""
        align = Gtk.Alignment()
        align.set(0, 0, 0, 0)

        install_button = Gtk.Button(_("Install"))
        install_button.connect("clicked", self.on_install_clicked)
        align.add(install_button)
        return align

    def get_notes(self):
        """Return the notes widget"""
        notes = self.script["notes"].strip()
        if not notes:
            return Gtk.Alignment()
        notes_label = InstallerLabel(notes)
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

    __gsignals__ = {"installer-selected": (GObject.SIGNAL_RUN_FIRST, None, (str, ))}

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
        "file-available": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "file-ready": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "file-unready": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, installer_file):
        super().__init__()
        self.installer_file = installer_file
        self.cache_to_pga = self.installer_file.uses_pga_cache()
        self.started = False
        self.start_func = None
        self.stop_func = None
        self.state_label = None  # Use this label to display status update
        self.set_margin_left(12)
        self.set_margin_right(12)
        self.provider = self.installer_file.provider
        self.popover = self.get_popover()
        self.file_provider_widget = None
        self.add(self.get_widgets())

    @property
    def is_ready(self):
        """Whether the file is ready to be downloaded / fetched from its provider"""
        if (
                self.provider in ("user", "pga")
                and not system.path_exists(self.installer_file.dest_file)
        ):
            return False
        return True

    def get_download_progress(self):
        """Return the widget for the download progress bar"""
        download_progress = DownloadProgressBox({
            "url": self.installer_file.url,
            "dest": self.installer_file.dest_file,
            "referer": self.installer_file.referer
        }, cancelable=True)
        download_progress.connect("complete", self.on_download_complete)
        download_progress.show()
        if (
                not self.installer_file.uses_pga_cache()
                and system.path_exists(self.installer_file.dest_file)
        ):
            os.remove(self.installer_file.dest_file)
        self.start_func = download_progress.start
        self.stop_func = download_progress.cancel
        return download_progress

    def get_file_provider_widget(self):
        """Return the widget used to track progress of file"""
        box = Gtk.VBox(spacing=6)
        if self.provider == "download":
            download_progress = self.get_download_progress()
            box.pack_start(download_progress, False, False, 0)
            return box
        if self.provider == "pga":
            url_label = InstallerLabel(
                "CACHED: %s" % gtk_safe(self.installer_file.human_url),
                wrap=False
            )
            box.pack_start(url_label, False, False, 6)
            return box
        if self.provider == "user":
            user_label = InstallerLabel(gtk_safe(self.installer_file.human_url))
            box.pack_start(user_label, False, False, 0)
        if self.provider == "steam":
            steam_installer = SteamInstaller(self.installer_file.url,
                                             self.installer_file.id)
            steam_installer.connect("game-installed", self.on_download_complete)
            steam_installer.connect("state-changed", self.on_state_changed)
            self.start_func = steam_installer.install_steam_game
            self.stop_func = steam_installer.stop_func

            steam_box = Gtk.HBox(spacing=6)
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

        return Gtk.Label(gtk_safe(self.installer_file.url))

    def get_popover(self):
        """Return the popover widget to select file source"""
        popover = Gtk.Popover()
        popover.add(self.get_popover_menu())
        popover.set_position(Gtk.PositionType.BOTTOM)
        return popover

    def get_source_radiobutton(self, last_widget, label, source):
        """Return a radio button for the popover menu"""
        button = Gtk.RadioButton.new_with_label_from_widget(last_widget, label)
        if self.provider == source:
            button.set_active(True)
        button.connect("toggled", self.on_source_changed, source)
        return button

    def get_popover_menu(self):
        """Create the menu going into the popover"""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        last_widget = None
        if "download" in self.installer_file.providers:
            download_button = self.get_source_radiobutton(last_widget, "Download", "download")
            vbox.pack_start(download_button, False, True, 10)
            last_widget = download_button
        if "pga" in self.installer_file.providers:
            pga_button = self.get_source_radiobutton(last_widget, "Use cache", "pga")
            vbox.pack_start(pga_button, False, True, 10)
            last_widget = pga_button
        user_button = self.get_source_radiobutton(last_widget, "Select file", "user")
        vbox.pack_start(user_button, False, True, 10)
        return vbox

    def replace_file_provider_widget(self):
        """Replace the file provider label and the source button with the actual widget"""
        self.file_provider_widget.destroy()
        widget_box = self.get_children()[0]
        if self.started:
            self.file_provider_widget = self.get_file_provider_widget()
            # Also remove the the source button
            for child in widget_box.get_children():
                child.destroy()
        else:
            self.file_provider_widget = self.get_file_provider_label()
        widget_box.pack_start(self.file_provider_widget, True, True, 0)
        widget_box.reorder_child(self.file_provider_widget, 0)
        widget_box.show_all()

    def on_source_changed(self, _button, source):
        """Change the source to a new provider, emit a new state"""
        if source == self.provider or not hasattr(self, "popover"):
            return
        self.provider = source
        self.replace_file_provider_widget()
        self.popover.popdown()
        button = self.popover.get_relative_to()
        if button:
            button.set_label(self.get_source_button_label())
        if self.provider == "user":
            self.emit("file-unready")
        else:
            self.emit("file-ready")

    def get_source_button_label(self):
        """Return the label for the source button"""
        if self.provider == "download":
            return "Download"
        if self.provider == "pga":
            return "Cache"
        if self.provider == "user":
            return "Local"
        raise ValueError("Unsupported provider %s" % self.provider)

    def get_file_provider_label(self):
        """Return the label displayed before the download starts"""
        if self.provider == "user":
            box = Gtk.VBox(spacing=6)
            location_entry = FileChooserEntry(
                self.installer_file.human_url,
                Gtk.FileChooserAction.OPEN,
                path=None
            )
            location_entry.entry.connect("changed", self.on_location_changed)
            location_entry.show()
            box.pack_start(location_entry, False, False, 0)
            if self.installer_file.uses_pga_cache(create=True):
                cache_option = Gtk.CheckButton("Cache file for future installations")
                cache_option.set_active(self.cache_to_pga)
                cache_option.connect("toggled", self.on_user_file_cached)
                box.pack_start(cache_option, False, False, 0)
            return box
        return InstallerLabel(gtk_safe(self.installer_file.human_url), wrap=False)

    def get_widgets(self):
        """Return the widget with the source of the file and a way to change its source"""
        box = Gtk.HBox(
            spacing=12,
            margin_top=6,
            margin_bottom=6
        )
        self.file_provider_widget = self.get_file_provider_label()
        box.pack_start(self.file_provider_widget, True, True, 0)
        source_box = Gtk.HBox()
        source_box.props.valign = Gtk.Align.START
        box.pack_start(source_box, False, False, 0)
        source_box.pack_start(InstallerLabel("Source:"), False, False, 0)
        button = Gtk.Button.new_with_label(self.get_source_button_label())
        button.connect("clicked", self.on_file_source_select)
        source_box.pack_start(button, False, False, 0)
        return box

    def on_file_source_select(self, button):
        """Open the popover to switch to a different source"""
        self.popover.set_relative_to(button)
        self.popover.show_all()
        self.popover.popup()

    def on_location_changed(self, widget):
        """Open a file picker when the browse button is clicked"""
        file_path = os.path.expanduser(widget.get_text())
        self.installer_file.dest_file = file_path
        if system.path_exists(file_path):
            self.emit("file-ready")
        else:
            self.emit("file-unready")

    def on_user_file_cached(self, checkbutton):
        """Enable or disable caching of user provided files"""
        self.cache_to_pga = checkbutton.get_active()

    def on_state_changed(self, _widget, state):
        """Update the state label with a new state"""
        self.state_label.set_text(state)

    def start(self):
        """Starts the download of the file"""
        self.started = True
        self.installer_file.prepare()
        self.replace_file_provider_widget()
        if self.provider in ("pga", "user") and self.is_ready:
            self.emit("file-available")
            self.cache_file()
            return
        if self.start_func:
            self.start_func()
        else:
            logger.info("No start function provided, this file can't be provided")

    def cache_file(self):
        """Copy file to the PGA cache"""
        if self.cache_to_pga:
            if os.path.dirname(self.installer_file.dest_file) == self.installer_file.cache_path:
                return
            shutil.copy(self.installer_file.dest_file, self.installer_file.cache_path)
            logger.debug("Copied %s to cache %s",
                         self.installer_file.dest_file,
                         self.installer_file.cache_path)

    def on_download_cancelled(self):
        """Handle cancellation of installers"""

    def on_download_complete(self, widget, _data=None):
        """Action called on a completed download."""
        if isinstance(widget, SteamInstaller):
            self.installer_file.dest_file = widget.get_steam_data_path()
        self.emit("file-available")
        self.cache_file()


class InstallerFilesBox(Gtk.ListBox):
    """List box presenting all files needed for an installer"""

    __gsignals__ = {
        "files-ready": (GObject.SIGNAL_RUN_LAST, None, (bool, )),
        "files-available": (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self, installer_files, parent):
        super().__init__()
        self.parent = parent
        self.installer_files = installer_files
        self.ready_files = set()
        self.available_files = set()
        self.installer_files_boxes = {}
        for installer_file in installer_files:
            installer_file_box = InstallerFileBox(installer_file)
            installer_file_box.connect("file-ready", self.on_file_ready)
            installer_file_box.connect("file-unready", self.on_file_unready)
            installer_file_box.connect("file-available", self.on_file_available)
            self.installer_files_boxes[installer_file.id] = installer_file_box
            self.add(installer_file_box)
            if installer_file_box.is_ready:
                self.ready_files.add(installer_file.id)
        self.show_all()
        self.check_files_ready()

    def start_all(self):
        """Start all downloads"""
        for file_id in self.installer_files_boxes:
            self.installer_files_boxes[file_id].start()

    @property
    def is_ready(self):
        """Return True if all files are ready to be fetched"""
        return len(self.ready_files) == len(self.installer_files)

    def check_files_ready(self):
        """Checks if all installer files are ready and emit a signal if so"""
        logger.debug("Files are ready? %s", self.is_ready)
        self.emit("files-ready", self.is_ready)

    def on_file_ready(self, widget):
        """Fired when a file has a valid provider.
        If the file is user provided, it must set to a valid path.
        """
        file_id = widget.installer_file.id
        self.ready_files.add(file_id)
        self.check_files_ready()

    def on_file_unready(self, widget):
        """Fired when a file can't be provided.
        Blocks the installer from continuing.
        """
        file_id = widget.installer_file.id
        self.ready_files.remove(file_id)
        self.check_files_ready()

    def on_file_available(self, widget):
        """A new file is available"""
        file_id = widget.installer_file.id
        self.available_files.add(file_id)
        if len(self.available_files) == len(self.installer_files):
            logger.info("All files available")
            self.emit("files-available")

    def get_game_files(self):
        """Return a mapping of the local files usable by the interpreter"""
        return {
            installer_file.id: installer_file.dest_file
            for installer_file in self.installer_files
        }
