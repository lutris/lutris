import os
from gettext import gettext as _

from gi.repository import Gtk

from lutris.cache import (
    delete_incomplete_installer_cache_entries,
    delete_installer_cache_entry,
    get_custom_cache_path,
    get_incomplete_installer_cache_entries,
    get_installer_cache_entries,
    save_custom_cache_path,
    validate_custom_cache_path,
)
from lutris.config import LutrisConfig
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.widget_generator import WidgetWarningMessageBox
from lutris.gui.dialogs import QuestionDialog
from lutris.gui.widgets.common import FileChooserEntry, Label
from lutris.runners.runner import Runner
from lutris.util.jobs import AsyncCall
from lutris.util.retroarch.firmware import scan_firmware_directory
from lutris.util.strings import gtk_safe, human_size


class StorageBox(BaseConfigBox):
    def populate(self):
        self.error_boxes = {
            "bios_path": StoragePathMessageBox(),
            "pga_cache_path": StoragePathMessageBox(),
        }
        self.cache_entry_checkbuttons = []

        self.add(self.get_section_label(_("Paths")))
        path_widgets = self.get_path_widgets()
        self.pack_start(self._get_framed_options_list_box(path_widgets), False, False, 0)
        self.pack_start(self.get_cached_installers_section(), False, False, 0)
        self.pack_start(self.get_incomplete_downloads_section(), False, False, 0)
        self.update_pga_cache_path_warning()

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
            },
            {
                "name": _("Emulator BIOS files location"),
                "setting": "bios_path",
                "default": "",
                "value": bios_path if bios_path else "",
                "help": _("The folder Lutris will search in for emulator BIOS files if needed"),
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

        if path_setting["setting"] in self.error_boxes:
            warning = self.error_boxes[path_setting["setting"]]
            wrapper.add(warning)

        wrapper.set_margin_end(16)
        wrapper.set_margin_left(16)
        wrapper.set_margin_bottom(16)

        return wrapper

    def is_bios_path_invalid(self, bios_path):
        if not bios_path:
            return bios_path, ""  # it's fine to not have a BIOS path
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
            return bios_path, _("Folder is too large (%s)") % human_size(bios_path_size)
        if bios_path_file_count > MAX_BIOS_FILES_IN_FOLDER:
            return bios_path, _("Too many files in folder")
        if bios_path_depth > MAX_BIOS_FOLDER_DEPTH:
            return bios_path, _("Folder is too deep")
        return bios_path, ""

    def bios_path_validated_cb(self, result, error):
        error_box = self.error_boxes["bios_path"]

        if error:
            error_box.show_markup(None)
            return

        bios_path, error_message = result

        error_box.show_markup(error_message)

        if not error_message:
            lutris_config = LutrisConfig()
            lutris_config.raw_system_config["bios_path"] = bios_path
            lutris_config.save()
            AsyncCall(scan_firmware_directory, None, bios_path)

    def on_file_chooser_changed(self, entry, setting):
        folder_path = entry.get_text()
        if setting["setting"] == "pga_cache_path":
            save_custom_cache_path(folder_path)
            self.update_pga_cache_path_warning()
        elif setting["setting"] == "game_path":
            lutris_config = LutrisConfig()
            lutris_config.raw_system_config["game_path"] = folder_path
            lutris_config.save()
        elif setting["setting"] == "bios_path":
            AsyncCall(self.is_bios_path_invalid, self.bios_path_validated_cb, folder_path)

    def update_pga_cache_path_warning(self):
        cache_path = get_custom_cache_path()
        if cache_path:
            valid, markup = validate_custom_cache_path(cache_path)
        else:
            valid, markup = True, None

        error_box = self.error_boxes["pga_cache_path"]
        error_box.show_markup(markup if markup and not valid else None)

    def get_cached_installers_section(self):
        box = Gtk.VBox(spacing=12, visible=True)
        box.pack_start(self.get_section_label(_("Cached installers")), False, False, 0)

        self.cached_installers_frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        box.pack_start(self.cached_installers_frame, False, False, 0)

        self.delete_cache_button = Gtk.Button(label=_("Delete selected cached installers"), visible=True)
        self.delete_cache_button.connect("clicked", self.on_delete_cached_installers_clicked)
        box.pack_start(self.delete_cache_button, False, False, 0)

        self.refresh_cached_installers_async()
        return box

    def refresh_cached_installers_async(self):
        self.display_cached_installers_loading()
        AsyncCall(get_installer_cache_entries, self.on_cached_installers_loaded)

    def display_cached_installers_loading(self):
        loading_label = Label()
        loading_label.set_markup("<i>%s</i>" % _("Scanning cached installers..."))
        loading_label.set_margin_top(12)
        loading_label.set_margin_bottom(12)
        loading_label.set_margin_left(12)
        loading_label.set_margin_right(12)
        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        list_box.add(Gtk.ListBoxRow(child=loading_label, visible=True, activatable=False))
        self.set_cached_installers_child(list_box)
        self.delete_cache_button.set_sensitive(False)

    def on_cached_installers_loaded(self, result, error):
        if error:
            self.refresh_cached_installers([])
            return
        self.refresh_cached_installers(result)

    def refresh_cached_installers(self, entries):
        self.cache_entry_checkbuttons = []

        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        if entries:
            for entry in entries:
                list_box.add(Gtk.ListBoxRow(child=self.get_cache_entry_row(entry), visible=True, activatable=False))
        else:
            empty_label = Label()
            empty_label.set_markup("<i>%s</i>" % _("No cached installers found."))
            empty_label.set_margin_top(12)
            empty_label.set_margin_bottom(12)
            empty_label.set_margin_left(12)
            empty_label.set_margin_right(12)
            list_box.add(Gtk.ListBoxRow(child=empty_label, visible=True, activatable=False))

        self.set_cached_installers_child(list_box)
        self.delete_cache_button.set_sensitive(bool(entries))

    def set_cached_installers_child(self, child):
        current_child = self.cached_installers_frame.get_child()
        if current_child:
            self.cached_installers_frame.remove(current_child)
        self.cached_installers_frame.add(child)
        self.cached_installers_frame.show_all()

    def get_cache_entry_row(self, entry):
        checkbutton = Gtk.CheckButton(visible=True, valign=Gtk.Align.CENTER)
        checkbutton.cache_entry_path = entry["path"]
        self.cache_entry_checkbuttons.append(checkbutton)

        label = Label()
        label.set_markup(
            "<b>{name}</b>\n{size}, {file_count} files\n<small>{path}</small>".format(
                name=gtk_safe(entry["name"]),
                size=human_size(entry["size"]),
                file_count=entry["file_count"],
                path=gtk_safe(entry["path"]),
            )
        )

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, visible=True)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        row.set_margin_left(12)
        row.set_margin_right(12)
        row.pack_start(checkbutton, False, False, 0)
        row.pack_start(label, True, True, 0)
        return row

    def on_delete_cached_installers_clicked(self, _button):
        selected_paths = [
            checkbutton.cache_entry_path for checkbutton in self.cache_entry_checkbuttons if checkbutton.get_active()
        ]
        if not selected_paths:
            return

        dlg = QuestionDialog(
            {
                "parent": self.get_toplevel(),
                "title": _("Delete cached installers?"),
                "question": _("Delete %d selected cached installer(s)?") % len(selected_paths),
            }
        )
        if dlg.result != Gtk.ResponseType.YES:
            return

        for path in selected_paths:
            delete_installer_cache_entry(path)
        self.refresh_cached_installers_async()

    def get_incomplete_downloads_section(self):
        box = Gtk.VBox(spacing=12, visible=True)
        box.pack_start(self.get_section_label(_("Incomplete installer downloads")), False, False, 0)

        self.incomplete_downloads_frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        box.pack_start(self.incomplete_downloads_frame, False, False, 0)

        self.delete_incomplete_button = Gtk.Button(label=_("Delete incomplete downloads"), visible=True)
        self.delete_incomplete_button.connect("clicked", self.on_delete_incomplete_downloads_clicked)
        box.pack_start(self.delete_incomplete_button, False, False, 0)

        self.refresh_incomplete_downloads_async()
        return box

    def refresh_incomplete_downloads_async(self):
        self.display_incomplete_downloads_loading()
        AsyncCall(get_incomplete_installer_cache_entries, self.on_incomplete_downloads_loaded)

    def display_incomplete_downloads_loading(self):
        loading_label = Label()
        loading_label.set_markup("<i>%s</i>" % _("Scanning incomplete downloads..."))
        loading_label.set_margin_top(12)
        loading_label.set_margin_bottom(12)
        loading_label.set_margin_left(12)
        loading_label.set_margin_right(12)
        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        list_box.add(Gtk.ListBoxRow(child=loading_label, visible=True, activatable=False))
        self.set_incomplete_downloads_child(list_box)
        self.delete_incomplete_button.set_sensitive(False)

    def on_incomplete_downloads_loaded(self, result, error):
        if error:
            self.refresh_incomplete_downloads([])
            return
        self.refresh_incomplete_downloads(result)

    def refresh_incomplete_downloads(self, entries):
        self.incomplete_download_entries = entries

        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        if entries:
            for entry in entries:
                list_box.add(
                    Gtk.ListBoxRow(child=self.get_incomplete_download_row(entry), visible=True, activatable=False)
                )
        else:
            empty_label = Label()
            empty_label.set_markup("<i>%s</i>" % _("No incomplete downloads found."))
            empty_label.set_margin_top(12)
            empty_label.set_margin_bottom(12)
            empty_label.set_margin_left(12)
            empty_label.set_margin_right(12)
            list_box.add(Gtk.ListBoxRow(child=empty_label, visible=True, activatable=False))

        self.set_incomplete_downloads_child(list_box)
        self.delete_incomplete_button.set_sensitive(bool(entries))

    def set_incomplete_downloads_child(self, child):
        current_child = self.incomplete_downloads_frame.get_child()
        if current_child:
            self.incomplete_downloads_frame.remove(current_child)
        self.incomplete_downloads_frame.add(child)
        self.incomplete_downloads_frame.show_all()

    def get_incomplete_download_row(self, entry):
        label = Label()
        label.set_markup(
            "<b>{kind}</b>\n{size}\n<small>{path}</small>".format(
                kind=gtk_safe(entry["kind"]),
                size=human_size(entry["size"]),
                path=gtk_safe(entry["path"]),
            )
        )

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, visible=True)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        row.set_margin_left(12)
        row.set_margin_right(12)
        row.pack_start(label, True, True, 0)
        return row

    def on_delete_incomplete_downloads_clicked(self, _button):
        if not self.incomplete_download_entries:
            return

        dlg = QuestionDialog(
            {
                "parent": self.get_toplevel(),
                "title": _("Delete incomplete downloads?"),
                "question": _("Delete %d incomplete download artifact(s)?")
                % len(self.incomplete_download_entries),
            }
        )
        if dlg.result != Gtk.ResponseType.YES:
            return

        delete_incomplete_installer_cache_entries([entry["path"] for entry in self.incomplete_download_entries])
        self.refresh_incomplete_downloads_async()


class StoragePathMessageBox(WidgetWarningMessageBox):
    def __init__(self, icon_name="dialog-error"):
        super().__init__(icon_name=icon_name)
