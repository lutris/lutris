import os
from gettext import gettext as _

from gi.repository import Gtk

from lutris.cache import get_custom_cache_path, save_custom_cache_path
from lutris.config import LutrisConfig
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.common import FileChooserEntry, Label
from lutris.runners.runner import Runner
from lutris.util.jobs import AsyncCall
from lutris.util.retroarch.firmware import scan_firmware_directory
from lutris.util.strings import human_size


class StorageBox(BaseConfigBox):
    bios_path_invalid_warning = Gtk.Label(label="WARNING: Invalid BIOS path")

    def populate(self):
        self.add(self.get_section_label(_("Paths")))
        path_widgets = self.get_path_widgets()
        self.pack_start(self._get_framed_options_list_box(path_widgets), False, False, 0)

    def get_path_widgets(self):
        widgets = []
        base_runner = Runner()
        bios_path = base_runner.config.system_config.get("bios_path")

        path_settings = [
            {
                "name": _("Game library"),
                "setting": "game_path",
                "default": os.path.expanduser("~/Games"),
                "value": base_runner.default_path,
                "help": _("The default folder where you install your games."),
                "has_warning": False,
            },
            {
                "name": _("Installer cache"),
                "setting": "pga_cache_path",
                "default": "",
                "value": get_custom_cache_path() or "",
                "help": _(
                    "If provided, files downloaded during game installs will be kept there\n"
                    "\nOtherwise, all downloaded files are discarded."
                ),
                "has_warning": False,
            },
            {
                "name": _("Emulator BIOS files location"),
                "setting": "bios_path",
                "default": "",
                "value": bios_path if bios_path else "",
                "help": _("The folder Lutris will search in for emulator BIOS files if needed"),
                "has_warning": True,
            },
        ]
        for path_setting in path_settings:
            widgets.append(self.get_directory_chooser(path_setting))
        return widgets

    def get_directory_chooser(self, path_setting):
        label = Label()
        label.set_markup("<b>%s</b>" % path_setting["name"])
        wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, visible=True)
        wrapper.set_margin_top(16)

        default_path = path_setting["default"]
        directory_chooser = FileChooserEntry(
            title=_("Select folder"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            warn_if_non_writable_parent=True,
            text=path_setting["value"],
            default_path=default_path,
        )
        directory_chooser.connect("changed", self.on_file_chooser_changed, path_setting)
        wrapper.pack_start(label, False, False, 0)
        wrapper.pack_start(directory_chooser, True, True, 0)
        if path_setting["help"]:
            help_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, visible=True)
            help_wrapper.add(wrapper)
            help_label = Label()
            help_label.set_markup("<i>%s</i>" % path_setting["help"])
            help_wrapper.add(help_label)
            wrapper = help_wrapper

        if path_setting["has_warning"]:
            wrapper.add(self.bios_path_invalid_warning)

        wrapper.set_margin_end(16)
        wrapper.set_margin_left(16)
        wrapper.set_margin_bottom(16)

        return wrapper

    def is_bios_path_invalid(self, bios_path):
        if not bios_path:
            return bios_path, "No path provided"
        MAX_BIOS_FOLDER_SIZE = 5e9
        MAX_BIOS_FILES_IN_FOLDER = 5000
        MAX_BIOS_FOLDER_DEPTH = 3

        bios_path_size = 0
        bios_path_file_count = 0
        bios_path_depth = 0

        for path, _dir_names, file_names in os.walk(bios_path):
            for file_name in file_names:
                file_path = f"{path}/{file_name}"
                if os.access(file_path, os.R_OK):
                    bios_path_size += os.path.getsize(file_path)
                    bios_path_file_count += 1
                    bios_path_depth = path[len(bios_path) :].count(os.sep)

        if bios_path_size > MAX_BIOS_FOLDER_SIZE:
            return bios_path, "Folder is too large (%s)" % human_size(bios_path_size)
        if bios_path_file_count > MAX_BIOS_FILES_IN_FOLDER:
            return bios_path, "Too many files in folder"
        if bios_path_depth > MAX_BIOS_FOLDER_DEPTH:
            return bios_path, "Folder is too deep"
        return bios_path, ""

    def bios_path_validated_cb(self, result, error):
        if error:
            self.bios_path_invalid_warning.set_visible(True)
            return

        bios_path, error_message = result

        self.bios_path_invalid_warning.set_visible(bool(error_message))
        self.bios_path_invalid_warning.set_text(error_message)

        if not error_message:
            lutris_config = LutrisConfig()
            lutris_config.raw_system_config["bios_path"] = bios_path
            lutris_config.save()
            AsyncCall(scan_firmware_directory, None, bios_path)

    def on_file_chooser_changed(self, entry, setting):
        folder_path = entry.get_text()
        if setting["setting"] == "pga_cache_path":
            save_custom_cache_path(folder_path)
        elif setting["setting"] == "game_path":
            lutris_config = LutrisConfig()
            lutris_config.raw_system_config["game_path"] = folder_path
            lutris_config.save()
        elif setting["setting"] == "bios_path":
            AsyncCall(self.is_bios_path_invalid, self.bios_path_validated_cb, folder_path)
