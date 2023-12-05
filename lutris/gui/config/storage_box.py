import os
from gettext import gettext as _

from gi.repository import Gtk

from lutris.cache import get_cache_path, save_cache_path
from lutris.config import LutrisConfig
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.common import FileChooserEntry, Label
from lutris.runners.runner import Runner


class StorageBox(BaseConfigBox):
    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Paths")))
        path_widgets = self.get_path_widgets()
        self.pack_start(self._get_framed_options_list_box(path_widgets), False, False, 12)

    def get_path_widgets(self):
        widgets = []
        base_runner = Runner()
        path_settings = [
            {
                "name": _("Game library"),
                "setting": "game_path",
                "default": os.path.expanduser("~/Games"),
                "value": base_runner.default_path,
                "help": _("The default folder where you install your games.")
            },
            {
                "name": "Installer cache",
                "setting": "pga_cache_path",
                "default": "",
                "value": get_cache_path(),
                "help": _(
                    "If provided, files downloaded during game installs will be kept there\n"
                    "\nOtherwise, all downloaded files are discarded."
                )
            }
        ]
        for path_setting in path_settings:
            widgets.append(self.get_directory_chooser(path_setting))
        return widgets

    def get_directory_chooser(self, path_setting):
        label = Label()
        label.set_markup("<b>%s</b>" % path_setting["name"])
        chooser_wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, visible=True)
        chooser_wrapper.set_margin_top(12)
        default_path = path_setting["default"]
        directory_chooser = FileChooserEntry(
            title=_("Select folder"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            text=path_setting["value"],
            default_path=default_path
        )
        directory_chooser.connect("changed", self.on_file_chooser_changed, path_setting)
        chooser_wrapper.pack_start(label, False, False, 0)
        chooser_wrapper.pack_start(directory_chooser, True, True, 0)
        if path_setting["help"]:
            help_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, visible=True)
            help_wrapper.add(chooser_wrapper)
            help_label = Label()
            help_label.set_markup("<i>%s</i>" % path_setting["help"])
            help_wrapper.add(help_label)
            help_wrapper.set_margin_bottom(12)
            return help_wrapper
        chooser_wrapper.set_margin_bottom(12)
        return chooser_wrapper

    def on_file_chooser_changed(self, entry, setting):
        text = entry.get_text()
        if text != entry.get_text():
            entry.set_text(text)
        if setting["setting"] == "pga_cache_path":
            save_cache_path(text)
        elif setting["setting"] == "game_path":
            lutris_config = LutrisConfig()
            lutris_config.raw_system_config["game_path"] = text
            lutris_config.save()
