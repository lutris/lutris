import hashlib
import json
import os
from gettext import gettext as _

from gi.repository import Gtk

from lutris.cache import get_cache_path, has_custom_cache_path, save_custom_cache_path
from lutris.config import LutrisConfig
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.common import FileChooserEntry, Label
from lutris.runners.runner import Runner
from lutris.util.system import get_md5_hash


def get_md5_from_file(filepath):
    with open(filepath, "rb") as file:
        file_data = file.read()
        result = hashlib.md5(file_data).hexdigest()

    return result


class StorageBox(BaseConfigBox):
    is_bios_path_invalid = False
    bios_path_invalid_warning = Gtk.Label(label="WARNING: Invalid BIOS path")

    def populate(self):
        self.add(self.get_section_label(_("Paths")))
        path_widgets = self.get_path_widgets()
        self.pack_start(self._get_framed_options_list_box(path_widgets), False, False, 0)

    def get_path_widgets(self):
        widgets = []
        base_runner = Runner()
        bios_path = base_runner.config.system_config.get("bios_path")
        self.is_bios_path_invalid = self.get_is_bios_path_invalid(bios_path)

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
                "value": get_cache_path() if has_custom_cache_path() else "",
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
        wrapper.set_margin_bottom(16)

        return wrapper

    def get_is_bios_path_invalid(self, bios_path):
        MAX_BIOS_PATH_SIZE = 5e9
        MAX_BIOS_PATH_FILE_COUNT = 5000
        MAX_BIOS_PATH_DEPTH = 3

        bios_path_size = 0
        bios_path_file_count = 0
        bios_path_depth = 0

        result = False

        for path, _dir_names, file_names in os.walk(bios_path):
            for file_name in file_names:
                file_path = f"{path}/{file_name}"
                if os.access(file_path, os.R_OK):
                    bios_path_size += os.path.getsize(file_path)
                    bios_path_file_count += 1
                    bios_path_depth = path[len(bios_path) :].count(os.sep)

        if (
            bios_path_size > MAX_BIOS_PATH_SIZE or
            bios_path_file_count > MAX_BIOS_PATH_FILE_COUNT or
            bios_path_depth > MAX_BIOS_PATH_DEPTH
        ):
            result = True

        self.bios_path_invalid_warning.set_visible(result)
        return result

    def on_file_chooser_changed(self, entry, setting):
        text = entry.get_text()
        if setting["setting"] == "pga_cache_path":
            save_custom_cache_path(text)
        elif setting["setting"] == "game_path":
            lutris_config = LutrisConfig()
            lutris_config.raw_system_config["game_path"] = text
            lutris_config.save()
        elif setting["setting"] == "bios_path":
            self.is_bios_path_invalid = self.get_is_bios_path_invalid(text)

            if not self.is_bios_path_invalid:
                lutris_config = LutrisConfig()
                lutris_config.raw_system_config["bios_path"] = text
                lutris_config.save()

                bios_files = []

                for path, _dir_names, file_names in os.walk(text):
                    for file_name in file_names:
                        file_path = f"{path}/{file_name}"

                        if os.access(file_path, os.R_OK):
                            bios_file = {}
                            bios_file["name"] = file_name
                            bios_file["size"] = os.path.getsize(file_path)
                            bios_file["date_created"] = os.path.getctime(file_path)
                            bios_file["date_modified"] = os.path.getmtime(file_path)
                            bios_file["md5_hash"] = get_md5_hash(file_path)

                            bios_files.append(bios_file)

                bios_files_cache_data = json.dumps(bios_files)
                bios_files_cache_path = os.path.expanduser("~/.cache/lutris/bios-files.json")
                with open(bios_files_cache_path, "w+") as bios_files_cache:
                    bios_files_cache.write(bios_files_cache_data)
