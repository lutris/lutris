"""Widgets for the installer window"""

import os
from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris.gui.installer.widgets import InstallerLabel
from lutris.gui.widgets.common import FileChooserEntry, KeyValueDropDown
from lutris.gui.widgets.utils import get_widget_children
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.installer.steam_installer import SteamInstaller
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import gtk_safe


class InstallerFileBox(Gtk.Box):
    """Container for an installer file downloader / selector"""

    __gsignals__ = {
        "file-available": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "file-ready": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "file-unready": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, installer_file):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.installer_file = installer_file
        self.cache_to_pga = self.installer_file.uses_pga_cache()
        self.started = False
        self.start_func = None
        self.stop_func = None
        self.state_label = None  # Use this label to display status update
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.provider = self.installer_file.default_provider
        self.file_provider_widget = None
        self.append(self.get_widgets())

    @property
    def is_ready(self):
        """Whether the file is ready to be downloaded / fetched from its provider"""
        return self.installer_file.is_ready(self.provider)

    def get_download_progress(self):
        """Return the widget for the download progress bar"""
        download_progress = self.installer_file.create_download_progress_box()
        download_progress.connect("complete", self.on_download_complete)
        download_progress.connect("cancel", self.on_download_cancelled)
        download_progress.connect("error", self.on_download_error)
        self.installer_file.remove_previous()
        return download_progress

    def get_file_provider_widget(self):
        """Return the widget used to track progress of file"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        if self.provider == "download":
            download_progress = self.get_download_progress()
            self.start_func = download_progress.start
            self.stop_func = download_progress.on_cancel_clicked
            box.append(download_progress)
            return box
        if self.provider == "pga":
            url_label = InstallerLabel("In cache: %s" % self.installer_file.get_label(), wrap=False)
            box.append(url_label)
            return box
        if self.provider == "user":
            user_label = InstallerLabel(gtk_safe(self.installer_file.human_url))
            box.append(user_label)
            return box
        # InstallerFileCollection should not have steam provider
        if self.provider == "steam":
            if isinstance(self.installer_file, InstallerFileCollection):
                raise RuntimeError("Installer file is type InstallerFileCollection and do not support 'steam' provider")
            steam_installer = SteamInstaller(self.installer_file.url, self.installer_file.id)
            steam_installer.game_installed.register(self.on_steam_game_installed)
            steam_installer.game_state_changed.register(self.on_steam_game_state_changed)
            self.start_func = steam_installer.install_steam_game
            self.stop_func = steam_installer.stop_func

            steam_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            steam_label = InstallerLabel(_("Steam game <b>{appid}</b>").format(appid=steam_installer.appid))
            info_box.append(steam_label)
            self.state_label = InstallerLabel("")
            info_box.append(self.state_label)
            steam_box.append(info_box)
            return steam_box
        raise ValueError("Invalid provider %s" % self.provider)

    def get_combobox(self):
        """Return the dropdown widget to select file source"""
        dropdown = KeyValueDropDown()
        if "download" in self.installer_file.providers:
            dropdown.append("download", _("Download"))
        if "pga" in self.installer_file.providers:
            dropdown.append("pga", _("Use Cache"))
        if "steam" in self.installer_file.providers:
            dropdown.append("steam", _("Steam"))
        if not (isinstance(self.installer_file, InstallerFileCollection) and self.installer_file.service == "amazon"):
            dropdown.append("user", _("Select File"))
        dropdown.connect("changed", self.on_source_changed)
        dropdown.set_active_id(self.provider)
        return dropdown

    def replace_file_provider_widget(self):
        """Replace the file provider label and the source button with the actual widget"""
        self.file_provider_widget.unparent()
        widget_box = self.get_first_child()
        if self.started:
            self.file_provider_widget = self.get_file_provider_widget()
            # Also remove the the source button
            for child in get_widget_children(widget_box):
                child.unparent()
        else:
            self.file_provider_widget = self.get_file_provider_label()
        self.file_provider_widget.set_hexpand(True)
        widget_box.prepend(self.file_provider_widget)

    def on_source_changed(self, dropdown):
        """Change the source to a new provider, emit a new state"""
        source = dropdown.get_active_id()
        if source is None:
            return
        if source == self.provider:
            return
        self.provider = source
        self.replace_file_provider_widget()
        if self.provider == "user":
            self.emit("file-unready")
        else:
            self.emit("file-ready")

    def get_file_provider_label(self):
        """Return the label displayed before the download starts"""
        if self.provider == "user":
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            label = InstallerLabel(self.installer_file.get_label())
            label.props.can_focus = True
            box.append(label)
            location_entry = FileChooserEntry(self.installer_file.human_url, Gtk.FileChooserAction.OPEN)
            location_entry.connect("changed", self.on_location_changed)
            box.append(location_entry)
            if self.installer_file.is_user_pga_caching_allowed:
                cache_option = Gtk.CheckButton(label=_("Cache file for future installations"))
                cache_option.set_active(self.cache_to_pga)
                cache_option.connect("toggled", self.on_user_file_cached)
                box.append(cache_option)
            return box
        return InstallerLabel(self.installer_file.get_label())

    def get_widgets(self):
        """Return the widget with the source of the file and a way to change its source"""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin_top=6, margin_bottom=6)
        self.file_provider_widget = self.get_file_provider_label()
        self.file_provider_widget.set_hexpand(True)
        box.append(self.file_provider_widget)
        source_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        source_box.props.valign = Gtk.Align.START
        box.append(source_box)

        aux_info = self.installer_file.auxiliary_info
        if aux_info:
            source_box.append(InstallerLabel(aux_info))
        source_box.append(InstallerLabel(_("Source:")))
        combobox = self.get_combobox()
        source_box.append(combobox)
        return box

    def on_location_changed(self, widget):
        """Open a file picker when the browse button is clicked"""
        file_path = os.path.expanduser(widget.get_text())
        self.installer_file.override_dest_file(file_path)
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

    def on_steam_game_state_changed(self, installer):
        """Update the state label with a new state"""
        self.state_label.set_text(installer.state)

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
            return self.start_func()

    def cache_file(self):
        """Copy file to the PGA cache"""
        if self.cache_to_pga:
            self.installer_file.save_to_cache()

    def on_download_cancelled(self, downloader):
        """Handle cancellation of installers"""
        logger.error("Download from %s cancelled", downloader)
        downloader.set_retry_button()

    def on_download_error(self, downloader, error):
        logger.error("Download from %s failed: %s", downloader, error)
        downloader.set_retry_button()

    def on_download_complete(self, widget, _data=None):
        """Action called on a completed download."""
        logger.info("Download completed")
        self.installer_file.check_hash()
        if isinstance(widget, SteamInstaller):
            self.installer_file.dest_file = widget.get_steam_data_path()
        else:
            self.cache_file()
        self.emit("file-available")

    def on_steam_game_installed(self, installer):
        self.installer_file.dest_file = installer.get_steam_data_path()
        self.emit("file-available")
