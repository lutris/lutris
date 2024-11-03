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

        self._generators = {
            "label": self._generate_label,
            "string": self._generate_string,
            "bool": self._generate_bool,
            "range": self._generate_range,
            "choice": self._generate_choice,
            "choice_with_entry": self._generate_choice_with_entry,
            "choice_with_search": self._generate_choice_with_search,
            "file": self._generate_file,
            "command_line": self._generate_command_line,
            "multiple_file": self._generate_multiple_file,
            "directory": self._generate_directory,
            "mapping": self._generate_mapping,
            # Backwards compatibility names (we're still using these though)
            "multiple": self._generate_multiple_file,
            "directory_chooser": self._generate_directory,
        }

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

        func = self._generators.get(option_type)

        if func:
            option_widget = func(option, value, default)
        else:
            raise ValueError("Unknown widget type %s" % option_type)
        self.option_widget = option_widget
        self.tooltip_default = self.tooltip_default or (default if isinstance(default, str) else None)

        return option_widget

    # Label
    def _generate_label(self, option, value, default):
        """Generate a simple label."""
        text = option["label"]
        label = Label(text)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, True, True, 0)
        return None

    # Entry
    def _generate_string(self, option, value, default):
        """Generate an entry box."""

        def on_changed(entry):
            """Action triggered for entry 'changed' signal."""
            self.changed.fire(option_name, entry.get_text())

        option_name = option["option"]
        label = option["label"]
        option_size = option.get("size", None)
        label = Label(label)
        self.wrapper.pack_start(label, False, False, 0)

        entry = Gtk.Entry()
        entry.set_text(value or default or "")
        entry.connect("changed", on_changed)
        expand = option_size != "small"
        self.wrapper.pack_start(entry, expand, expand, 0)
        return entry

    # Switch
    def _generate_bool(self, option, value, default):
        """Generate a checkbox."""

        def on_notify_active(widget, _gparam):
            """Action for the checkbox's toggled signal."""
            self.changed.fire(option_name, widget.get_active())

        option_name = option["option"]
        label = Label(option["label"])
        self.wrapper.pack_start(label, False, False, 0)

        switch = Gtk.Switch()
        if value is None:
            switch.set_active(default)
        else:
            switch.set_active(value)
        switch.connect("notify::active", on_notify_active)
        switch.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(switch, False, False, 0)

        self.tooltip_default = "Enabled" if default else "Disabled"
        return switch

    # SpinButton
    def _generate_range(self, option, value, default):
        """Generate a ranged spin button."""

        def on_changed(widget):
            """Action triggered on spin button 'changed' signal."""
            new_value = widget.get_value_as_int()
            self.changed.fire(option_name, new_value)

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
        spin_button.connect("changed", on_changed)
        label = Label(label)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(spin_button, True, True, 0)
        return spin_button

    # ComboBox
    def _generate_choice(self, option, value, default, has_entry=False):
        """Generate a combobox (drop-down menu)."""

        def populate_combobox_choices():
            expanded, tooltip_default = expand_combobox_choices()
            for choice in expanded:
                liststore.append(choice)

            if tooltip_default:
                self.tooltip_default = tooltip_default

        def expand_combobox_choices():
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

        def on_combobox_scroll(widget, _event):
            """Prevents users from accidentally changing configuration values
            while scrolling down dialogs.
            """
            widget.stop_emission_by_name("scroll-event")
            return False

        def on_combobox_change(widget):
            """Action triggered on combobox 'changed' signal."""
            list_store = widget.get_model()
            active = widget.get_active()
            option_value = None
            if active < 0:
                if widget.get_has_entry():
                    option_value = widget.get_child().get_text()
            else:
                option_value = list_store[active][1]
            self.changed.fire(option_name, option_value)

        option_name = option["option"]
        choices = option["choices"]
        label = option["label"]
        liststore = Gtk.ListStore(str, str)
        populate_combobox_choices()
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

        expanded, _tooltip_default = expand_combobox_choices()
        if value in [v for _k, v in expanded]:
            combobox.set_active_id(value)
        elif has_entry:
            for ch in combobox.get_children():
                if isinstance(ch, Gtk.Entry):
                    ch.set_text(value or "")
                    break
        else:
            combobox.set_active_id(default)

        combobox.connect("changed", on_combobox_change)
        combobox.connect("scroll-event", on_combobox_scroll)
        label = Label(label)
        combobox.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(combobox, True, True, 0)
        return combobox

    # ComboBox
    def _generate_choice_with_entry(self, option, value, default):
        return self._generate_choice(option, value, default, has_entry=True)

    # ComboBox
    def _generate_choice_with_search(self, option, value, default):
        """Generate a searchable combo box"""

        def on_changed(_widget, value):
            self.changed.fire(option_name, value)

        option_name = option["option"]
        choice_func = option["choices"]
        label = option["label"]
        combobox = SearchableCombobox(choice_func, value or default)
        combobox.connect("changed", on_changed)
        self.wrapper.pack_start(Label(label), False, False, 0)
        self.wrapper.pack_start(combobox, True, True, 0)
        return combobox

    # FileChooserEntry
    def _generate_file(self, option, path=None, default_path=None, shell_quoting=False):
        """Generate a file chooser button to select a file."""

        def on_changed(entry):
            """Action triggered when the field's content changes."""
            text = entry.get_text()
            self.changed.fire(option_name, text)

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

        file_chooser.connect("changed", on_changed)
        return file_chooser

    # FileChooserEntry
    def _generate_command_line(self, option, path=None, default_path=None):
        return self._generate_file(option, path, default_path, shell_quoting=True)

    # TreeView
    def _generate_multiple_file(self, option, value, default):
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

    # FileChooserEntry
    def _generate_directory(self, option, path=None, default_path=None):
        """Generate a file chooser button to select a directory."""

        def on_changed(entry):
            """Action triggered when the field's content changes."""
            text = entry.get_text()
            self.changed.fire(option_name, text)

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
        directory_chooser.connect("changed", on_changed)
        directory_chooser.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(directory_chooser, True, True, 0)
        return directory_chooser

    # EditableGrid
    def _generate_mapping(self, option, value, default):
        """Adds an editable grid widget"""

        def on_changed(widget):
            values = dict(widget.get_data())
            self.changed.fire(option_name, values)

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
        grid.connect("changed", on_changed, option_name)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(grid, True, True, 0)
        return grid
