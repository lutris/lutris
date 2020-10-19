"""Widgets for the installer window"""
import os
from gettext import gettext as _
from urllib.parse import urlparse

from gi.repository import GObject, Gtk

from lutris.cache import save_to_cache
from lutris.gui.installer.widgets import InstallerLabel
from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.widgets.download_progress import DownloadProgressBox
from lutris.installer.steam_installer import SteamInstaller
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import add_url_tags, gtk_safe


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
            url_label = InstallerLabel("In cache: %s" % self.get_file_label(), wrap=False)
            box.pack_start(url_label, False, False, 6)
            return box
        if self.provider == "user":
            user_label = InstallerLabel(gtk_safe(self.installer_file.human_url))
            box.pack_start(user_label, False, False, 0)
            return box
        if self.provider == "steam":
            steam_installer = SteamInstaller(self.installer_file.url,
                                             self.installer_file.id)
            steam_installer.connect("game-installed", self.on_download_complete)
            steam_installer.connect("state-changed", self.on_state_changed)
            self.start_func = steam_installer.install_steam_game
            self.stop_func = steam_installer.stop_func

            steam_box = Gtk.HBox(spacing=6)
            info_box = Gtk.VBox(spacing=6)
            steam_label = InstallerLabel(_("Steam game for {platform} (appid: <b>{appid}</b>)").format(
                platform=steam_installer.platform,
                appid=steam_installer.appid
            ))
            info_box.add(steam_label)
            self.state_label = InstallerLabel("")
            info_box.add(self.state_label)
            steam_box.add(info_box)
            return steam_box
        return Gtk.Label("?")

    def get_file_label(self):
        """Return a human readable label for installer files"""
        url = self.installer_file.url
        if url.startswith("http"):
            parsed = urlparse(url)
            label = "%s on %s" % (self.installer_file.filename, parsed.netloc)
        elif url.startswith("N/A"):
            label = url[3:].lstrip(":")
        else:
            label = url
        return add_url_tags(gtk_safe(label))

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
            download_button = self.get_source_radiobutton(last_widget, _("Download"), "download")
            vbox.pack_start(download_button, False, True, 10)
            last_widget = download_button
        if "pga" in self.installer_file.providers:
            pga_button = self.get_source_radiobutton(last_widget, _("Use cache"), "pga")
            vbox.pack_start(pga_button, False, True, 10)
            last_widget = pga_button
        user_button = self.get_source_radiobutton(last_widget, _("Select file"), "user")
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
        provider_labels = {
            "download": _("Download"),
            "pga": _("Cache"),
            "user": _("Local"),
            "steam": _("Steam"),
        }
        if self.provider in provider_labels:
            return provider_labels[self.provider]
        raise ValueError("Unsupported provider %s" % self.provider)

    def get_file_provider_label(self):
        """Return the label displayed before the download starts"""
        if self.provider == "user":
            box = Gtk.VBox(spacing=6)
            label = InstallerLabel(self.get_file_label())
            label.props.can_focus = True
            box.pack_start(label, False, False, 0)
            location_entry = FileChooserEntry(
                self.installer_file.human_url,
                Gtk.FileChooserAction.OPEN,
                path=None
            )
            location_entry.entry.connect("changed", self.on_location_changed)
            location_entry.show()
            box.pack_start(location_entry, False, False, 0)
            if self.installer_file.uses_pga_cache(create=True):
                cache_option = Gtk.CheckButton(_("Cache file for future installations"))
                cache_option.set_active(self.cache_to_pga)
                cache_option.connect("toggled", self.on_user_file_cached)
                box.pack_start(cache_option, False, False, 0)
            return box
        return InstallerLabel(self.get_file_label())

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
        source_box.pack_start(InstallerLabel(_("Source:")), False, False, 0)
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
            save_to_cache(self.installer_file.dest_file, self.installer_file.cache_path)

    def on_download_cancelled(self):
        """Handle cancellation of installers"""

    def on_download_complete(self, widget, _data=None):
        """Action called on a completed download."""
        if isinstance(widget, SteamInstaller):
            self.installer_file.dest_file = widget.get_steam_data_path()
        self.emit("file-available")
        self.cache_file()
