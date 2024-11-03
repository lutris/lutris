"""Widget generators and their signal handlers"""

# Standard Library
# pylint: disable=no-member,too-many-public-methods
import os
from gettext import gettext as _
from typing import Optional

# Third Party Libraries
from gi.repository import Gdk, Gtk

from lutris.config import LutrisConfig
from lutris.gui.widgets import NotificationSource
from lutris.gui.widgets.common import EditableGrid, FileChooserEntry, Label
from lutris.gui.widgets.searchable_combobox import SearchableCombobox
from lutris.util.log import logger


class WidgetGenerator:
    """This class generates widgets for an options screen. It even adds the widgets
    to a 'wrapper' you supply. The specific widgets and generated according to an options
    dict, and there's a NotificationSource for whenever the widget changes a value (you can supply this
    explicitly to avoid having one per widget, too)."""

    def __init__(self, directory: str = None, changed: NotificationSource = None) -> None:
        self.directory = directory
        self.changed = changed or NotificationSource()  # takes option_key, new_value
        self.wrapper: Optional[Gtk.Widget] = None
        self.default_value = None
        self.tooltip_default: Optional[str] = None
        self.option_widget: Optional[Gtk.Widget] = None

    def generate_widget(self, wrapper, option, value):  # noqa: C901
        """Call the right generation method depending on option type."""
        # pylint: disable=too-many-branches
        self.wrapper = wrapper
        self.tooltip_default = None
        self.option_widget = None
        option_type = option["type"]

        default = option.get("default")
        if callable(default):
            default = default()
        self.default_value = default

        if option_type == "choice":
            option_widget = self.generate_combobox(option, value, default)
        elif option_type == "choice_with_entry":
            option_widget = self.generate_entry_combobox(option, value, default)
        elif option_type == "choice_with_search":
            option_widget = self.generate_searchable_combobox(option, value, default)
        elif option_type == "bool":
            option_widget = self.generate_checkbox(option, value, default)
        elif option_type == "range":
            option_widget = self.generate_range(option, value, default)
        elif option_type == "string":
            option_widget = self.generate_entry(option, value, default)
        elif option_type == "directory_chooser":
            option_widget = self.generate_directory_chooser(option, value, default)
        elif option_type == "file":
            option_widget = self.generate_file_chooser(option, value, default)
        elif option_type == "command_line":
            option_widget = self.generate_command_line(option, value, default)
        elif option_type == "multiple":
            option_widget = self.generate_multiple_file_chooser(option, value, default)
        elif option_type == "label":
            option_widget = self.generate_label(option, value, default)
        elif option_type == "mapping":
            option_widget = self.generate_editable_grid(option, value, default)
        else:
            raise ValueError("Unknown widget type %s" % option_type)
        self.option_widget = option_widget
        self.tooltip_default = self.tooltip_default or (default if isinstance(default, str) else None)

        return option_widget

    # Label
    def generate_label(self, option, value, default):
        """Generate a simple label."""
        text = option["label"]
        label = Label(text)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, True, True, 0)
        return None

    # Checkbox
    def generate_checkbox(self, option, value, default):
        """Generate a checkbox."""

        label = Label(option["label"])
        self.wrapper.pack_start(label, False, False, 0)

        switch = Gtk.Switch()
        if value is None:
            switch.set_active(default)
        else:
            switch.set_active(value)
        switch.connect("notify::active", self.checkbox_toggle, option["option"])
        switch.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(switch, False, False, 0)

        self.tooltip_default = "Enabled" if default else "Disabled"
        return switch

    def checkbox_toggle(self, widget, _gparam, option_name):
        """Action for the checkbox's toggled signal."""
        self.changed.fire(option_name, widget.get_active())

    # Entry
    def generate_entry(self, option, value, default):
        """Generate an entry box."""
        option_name = option["option"]
        label = option["label"]
        option_size = option.get("size", None)
        label = Label(label)
        self.wrapper.pack_start(label, False, False, 0)

        entry = Gtk.Entry()
        entry.set_text(value or default or "")
        entry.connect("changed", self.entry_changed, option_name)
        expand = option_size != "small"
        self.wrapper.pack_start(entry, expand, expand, 0)
        return entry

    def entry_changed(self, entry, option_name):
        """Action triggered for entry 'changed' signal."""
        self.changed.fire(option_name, entry.get_text())

    def generate_searchable_combobox(self, option, value, default):
        """Generate a searchable combo box"""
        option_name = option["option"]
        choice_func = option["choices"]
        label = option["label"]
        combobox = SearchableCombobox(choice_func, value or default)
        combobox.connect("changed", self.on_searchable_entry_changed, option_name)
        self.wrapper.pack_start(Label(label), False, False, 0)
        self.wrapper.pack_start(combobox, True, True, 0)
        return combobox

    def on_searchable_entry_changed(self, combobox, value, key):
        self.changed.fire(key, value)

    def _populate_combobox_choices(self, liststore, choices, value, default):
        expanded, tooltip_default = self._expand_combobox_choices(choices, value, default)
        for choice in expanded:
            liststore.append(choice)

        if tooltip_default:
            self.tooltip_default = tooltip_default

    @staticmethod
    def _expand_combobox_choices(choices, value, default):
        expanded = []
        tooltip_default = None
        has_value = False
        for choice in choices:
            if isinstance(choice, str):
                choice = (choice, choice)
            if choice[1] == value:
                has_value = True
            if choice[1] == default:
                tooltip_default = choice[0]
                choice = (_("%s (default)") % choice[0], choice[1])
            expanded.append(choice)
        if not has_value and value:
            expanded.insert(0, (value + " (invalid)", value))
        return expanded, tooltip_default

    # ComboBox
    def generate_entry_combobox(self, option, value, default):
        return self.generate_combobox(option, value, default, has_entry=True)

    # ComboBox
    def generate_combobox(self, option, value, default, has_entry=False):
        """Generate a combobox (drop-down menu)."""
        option_name = option["option"]
        choices = option["choices"]
        label = option["label"]
        liststore = Gtk.ListStore(str, str)
        self._populate_combobox_choices(liststore, choices, value, default)
        # With entry ("choice_with_entry" type)
        if has_entry:
            combobox = Gtk.ComboBox.new_with_model_and_entry(liststore)
            combobox.set_entry_text_column(0)
        # No entry ("choice" type)
        else:
            combobox = Gtk.ComboBox.new_with_model(liststore)
            cell = Gtk.CellRendererText()
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, "text", 0)

        combobox.set_id_column(1)

        expanded, _tooltip_default = self._expand_combobox_choices(choices, value, default)
        if value in [v for _k, v in expanded]:
            combobox.set_active_id(value)
        elif has_entry:
            for ch in combobox.get_children():
                if isinstance(ch, Gtk.Entry):
                    ch.set_text(value or "")
                    break
        else:
            combobox.set_active_id(default)

        combobox.connect("changed", self.on_combobox_change, option_name)
        combobox.connect("scroll-event", self._on_combobox_scroll)
        label = Label(label)
        combobox.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(combobox, True, True, 0)
        return combobox

    @staticmethod
    def _on_combobox_scroll(combobox, _event):
        """Prevents users from accidentally changing configuration values
        while scrolling down dialogs.
        """
        combobox.stop_emission_by_name("scroll-event")
        return False

    def on_combobox_change(self, combobox, option):
        """Action triggered on combobox 'changed' signal."""
        list_store = combobox.get_model()
        active = combobox.get_active()
        option_value = None
        if active < 0:
            if combobox.get_has_entry():
                option_value = combobox.get_child().get_text()
        else:
            option_value = list_store[active][1]
        self.changed.fire(option, option_value)

    # Range
    def generate_range(self, option, value, default):
        """Generate a ranged spin button."""

        option_name = option["option"]
        min_val = option["min"]
        max_val = option["max"]
        label = option["label"]

        adjustment = Gtk.Adjustment(float(min_val), float(min_val), float(max_val), 1, 0, 0)
        spin_button = Gtk.SpinButton()
        spin_button.set_adjustment(adjustment)
        if value:
            spin_button.set_value(value)
        elif default:
            spin_button.set_value(default)
        spin_button.connect("changed", self.on_spin_button_changed, option_name)
        label = Label(label)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(spin_button, True, True, 0)
        return spin_button

    def on_spin_button_changed(self, spin_button, option):
        """Action triggered on spin button 'changed' signal."""
        value = spin_button.get_value_as_int()
        self.changed.fire(option, value)

    def generate_command_line(self, option, path=None, default_path=None):
        return self.generate_file_chooser(option, path, default_path, shell_quoting=True)

    # File chooser
    def generate_file_chooser(self, option, path=None, default_path=None, shell_quoting=False):
        """Generate a file chooser button to select a file."""
        option_name = option["option"]
        label = Label(option["label"])
        warn_if_non_writable_parent = bool(option.get("warn_if_non_writable_parent"))

        if not path:
            path = default_path

        if "default_path" in option:
            lutris_config = LutrisConfig()
            chooser_default_path = lutris_config.system_config.get(option["default_path"])
        else:
            chooser_default_path = self.directory

        file_chooser = FileChooserEntry(
            title=_("Select file"),
            action=Gtk.FileChooserAction.OPEN,
            warn_if_non_writable_parent=warn_if_non_writable_parent,
            text=path,
            default_path=chooser_default_path,
            shell_quoting=shell_quoting,
        )

        if path:
            # If path is relative, complete with game dir
            if not os.path.isabs(path):
                path = os.path.expanduser(path)
                if not os.path.isabs(path):
                    if self.directory:
                        path = os.path.join(self.directory, path)
            file_chooser.entry.set_text(path)

        file_chooser.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(file_chooser, True, True, 0)

        file_chooser.connect("changed", self._on_chooser_file_set, option_name)
        return file_chooser

    # Directory chooser
    def generate_directory_chooser(self, option, path=None, default_path=None):
        """Generate a file chooser button to select a directory."""
        label = Label(option["label"])
        option_name = option["option"]
        warn_if_non_writable_parent = bool(option.get("warn_if_non_writable_parent"))

        if not path:
            path = default_path

        chooser_default_path = None
        if not path and self.directory:
            chooser_default_path = self.directory
        directory_chooser = FileChooserEntry(
            title=_("Select folder"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            warn_if_non_writable_parent=warn_if_non_writable_parent,
            text=path,
            default_path=chooser_default_path,
        )
        directory_chooser.connect("changed", self._on_chooser_file_set, option_name)
        directory_chooser.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(directory_chooser, True, True, 0)
        return directory_chooser

    def _on_chooser_file_set(self, entry, option):
        """Action triggered when the field's content changes."""
        text = entry.get_text()
        if text != entry.get_text():
            entry.set_text(text)
        self.changed.fire(option, text)

    # Editable grid
    def generate_editable_grid(self, option, value, default):
        """Adds an editable grid widget"""

        option_name = option["option"]
        label = option["label"]
        value = value or default or {}
        try:
            value = list(value.items())
        except AttributeError:
            logger.error("Invalid value of type %s passed to grid widget: %s", type(value), value)
            value = {}
        label = Label(label)

        grid = EditableGrid(value, columns=["Key", "Value"])
        grid.connect("changed", self._on_grid_changed, option_name)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(grid, True, True, 0)
        return grid

    def _on_grid_changed(self, grid, option):
        values = dict(grid.get_data())
        self.changed.fire(option, values)

    # Multiple file selector
    def generate_multiple_file_chooser(self, option, value, default):
        """Generate a multiple file selector."""

        def on_add_files_clicked(_widget):
            """Create and run multi-file chooser dialog."""

            dialog = Gtk.FileChooserNative.new(
                _("Select files"),
                None,
                Gtk.FileChooserAction.OPEN,
                _("_Add"),
                _("_Cancel"),
            )
            dialog.set_select_multiple(True)

            files = [row[0] for row in files_list_store]
            first_file_dir = os.path.dirname(files[0]) if files else None
            dialog.set_current_folder(first_file_dir or self.directory or os.path.expanduser("~"))
            response = dialog.run()
            if response == Gtk.ResponseType.ACCEPT:
                for filename in dialog.get_filenames():
                    if filename not in files:
                        files_list_store.append([filename])
                        files.append(filename)
                self.changed.fire(option_name, files)
            dialog.destroy()

        def on_files_treeview_keypress(treeview, event):
            """Action triggered when a row is deleted from the filechooser."""
            if event.keyval == Gdk.KEY_Delete:
                selection = treeview.get_selection()
                (model, treepaths) = selection.get_selected_rows()
                for treepath in treepaths:
                    treeiter = model.get_iter(treepath)
                    model.remove(treeiter)

                    files = [row[0] for row in files_list_store]
                    self.changed.fire(option_name, files)

        option_name = option["option"]
        label = option["label"]

        files_list_store = Gtk.ListStore(str)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        label = Label(label + ":")
        label.set_halign(Gtk.Align.START)
        button = Gtk.Button(_("Add Files"))
        button.connect("clicked", on_add_files_clicked)
        button.set_margin_left(10)
        vbox.pack_start(label, False, False, 5)
        vbox.pack_end(button, False, False, 0)

        if not value:
            value = default

        if value:
            if isinstance(value, str):
                files = [value]
            else:
                files = value
        else:
            files = []
        for filename in files:
            files_list_store.append([filename])
        cell_renderer = Gtk.CellRendererText()
        files_treeview = Gtk.TreeView(files_list_store)
        files_column = Gtk.TreeViewColumn(_("Files"), cell_renderer, text=0)
        files_treeview.append_column(files_column)
        files_treeview.connect("key-press-event", on_files_treeview_keypress)
        treeview_scroll = Gtk.ScrolledWindow()
        treeview_scroll.set_min_content_height(130)
        treeview_scroll.set_margin_left(10)
        treeview_scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        treeview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        treeview_scroll.add(files_treeview)

        vbox.pack_start(treeview_scroll, True, True, 0)
        self.wrapper.pack_start(vbox, True, True, 0)
        return vbox
