"""Widget generators and their signal handlers"""

# Standard Library
# pylint: disable=no-member,too-many-public-methods
import os
from abc import ABC, abstractmethod
from gettext import gettext as _
from typing import Any, Callable, Dict, List, Optional

# Third Party Libraries
from gi.repository import Gdk, Gtk

from lutris.config import LutrisConfig
from lutris.gui.widgets import NotificationSource
from lutris.gui.widgets.common import EditableGrid, FileChooserEntry, Label
from lutris.gui.widgets.searchable_combobox import SearchableCombobox
from lutris.util.log import logger
from lutris.util.strings import gtk_safe


class WidgetGenerator(ABC):
    """This class generates widgets for an options screen. It even adds the widgets
    to a 'wrapper' you supply. The specific widgets and generated according to an options
    dict, and there's a NotificationSource for whenever the widget changes a value (you can supply this
    explicitly to avoid having one per widget, too)."""

    GeneratorFunction = Callable[[Dict[str, Any], Any, Any], Optional[Gtk.Widget]]

    def __init__(self) -> None:
        self._default_directory: Optional[str] = None
        self.changed = NotificationSource()  # takes option_key, new_value

        # These are outputs sets by generate_widget()
        self.wrapper: Optional[Gtk.Widget] = None
        self.default_value = None
        self.tooltip_default: Optional[str] = None
        self.option_widget: Optional[Gtk.Widget] = None
        self.option_container: Optional[Gtk.Widget] = None
        self.message_widgets: List[Gtk.Widget] = []
        self.message_updaters: List[Callable[[Any], bool]] = []

        self._generators: Dict[str, WidgetGenerator.GeneratorFunction] = {
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

    @property
    def default_directory(self) -> str:
        """This is the directory selected by default by file and directory choosers."""
        if not self._default_directory:
            lutris_config = LutrisConfig()
            self._default_directory = lutris_config.system_config.get("game_path") or os.path.expanduser("~")
        return self._default_directory

    @default_directory.setter
    def default_directory(self, new_dir: str) -> None:
        self._default_directory = new_dir

    def generate_container(self, option: Dict[str, Any], value: Any, wrapper: Gtk.Box = None) -> Optional[Gtk.Widget]:
        option_widget = self.generate_widget(option, value, wrapper)
        if self.wrapper:
            self.option_container = self.create_option_container(self.wrapper)

        return option_widget

    def generate_widget(self, option: Dict[str, Any], value: Any, wrapper: Gtk.Box = None) -> Optional[Gtk.Widget]:
        """This creates a wrapper box and a label and widget within it according to the options dict
        given. The option widget itself, is returned, but this method also sets attributes on the
        generator. You get 'wrapper', 'default_value', 'tooltip_default' and 'option_widget' which restates
        the return value. This returns None if the entire option should be omitted."""
        option_type = option["type"]
        option_key = option["option"]
        default = option.get("default")
        if callable(default):
            default = default()

        self.default_value = default
        self.tooltip_default = None
        self.option_widget = None
        self.option_container = None
        self.message_widgets.clear()
        self.message_updaters.clear()

        if wrapper:
            # Destroy and recreate option widget
            children = wrapper.get_children()
            for child in children:
                child.destroy()
            self.wrapper = wrapper
        else:
            self.wrapper = self.create_wrapper_box(option, value, default)

            if not self.wrapper:
                return None

        func = self._generators.get(option_type)

        if func:
            option_widget = func(option, value, default)
        else:
            raise ValueError("Unknown widget type %s" % option_type)

        self.option_widget = option_widget
        self.tooltip_default = self.tooltip_default or (default if isinstance(default, str) else None)

        # Tooltip
        tooltip = self.get_tooltip(option, value, default)
        if tooltip:
            self.wrapper.props.has_tooltip = True
            self.wrapper.connect("query-tooltip", self.on_query_tooltip, tooltip)

        if "error" in option:
            error = ConfigErrorBox(option["error"], option_key, self.wrapper)
            self.message_widgets.append(error)
            self.message_updaters.append(error.update_warning)

        if "warning" in option:
            warning = ConfigWarningBox(option["warning"], option_key)
            self.message_widgets.append(warning)
            self.message_updaters.append(warning.update_warning)

        if option_widget:
            option_widget.show_all()
        return option_widget

    def create_wrapper_box(self, option: Dict[str, Any], value: Any, default: Any) -> Optional[Gtk.Box]:
        """This creates the wrapper, which becomes the 'wrapper' attribute and which build_option_widget()
        populates. Returns None if the option is not visible; in that case no widget is generated either."""

        visible = option.get("visible")
        if visible is None:
            visible = True
        elif callable(visible):
            visible = visible()

        if not visible:
            # If invisible, there's no wrapper, and no widget!
            return None

        return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin_bottom=6, visible=True)

    def create_option_container(self, wrapper: Gtk.Widget) -> Gtk.Widget:
        """This creates a wrapper box around the widget wrapper, to support additional controls. The
        base implementation wraps 'wrapper' in a Box with the error and warning widgets; if
        there are none it just returns 'wrapper'."""

        if self.message_widgets:
            option_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
            option_container.pack_start(wrapper, False, False, 0)

            for error_widget in self.message_widgets:
                option_container.pack_start(error_widget, False, False, 0)

            return option_container
        else:
            return wrapper

    def get_tooltip(self, option: Dict[str, Any], value: Any, default: Any):
        tooltip = option.get("help")
        if isinstance(self.tooltip_default, str):
            tooltip = tooltip + "\n\n" if tooltip else ""
            tooltip += _("<b>Default</b>: ") + self.tooltip_default
        return tooltip

    def build_option_widget(
        self, option: Dict[str, Any], widget: Optional[Gtk.Widget], no_label: bool = False, expand: bool = True
    ) -> Optional[Gtk.Widget]:
        """This is called by the generator methods to place their widget into the wrapper, usually with
        a label taken from 'option'.

        The default labeling and placement is suitable for our ConfigBoxes, but we override this to
        get a different layout for PreferencesBox.

        Some generators do their own labelling, and pass True for no_label; this method will
        pack the widget with no label in that case.

        This method returns the widget."""
        if self.wrapper:
            if not no_label and "label" in option:
                label = option["label"]
                label = Label(label)
                self.wrapper.pack_start(label, False, False, 0)

            if widget:
                option_size = option.get("size", None)
                if option_size:
                    expand = option_size != "small"

                self.wrapper.pack_start(widget, expand, expand, 0)
        return widget

    @abstractmethod
    def get_setting(self, option_key: str) -> Any:
        raise NotImplementedError()

    # Label
    def _generate_label(self, option, value, default):
        """Generate a simple label."""
        text = option["label"]
        label = Label(text)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        return self.build_option_widget(option, label, no_label=True)

    # Entry
    def _generate_string(self, option, value, default):
        """Generate an entry box."""

        def on_changed(entry):
            """Action triggered for entry 'changed' signal."""
            self.changed.fire(option_key, entry.get_text())

        option_key = option["option"]

        entry = Gtk.Entry()
        entry.set_text(value or default or "")
        entry.connect("changed", on_changed)
        return self.build_option_widget(option, entry)

    # Switch
    def _generate_bool(self, option, value, default):
        """Generate a switch."""

        def on_notify_active(widget, _gparam):
            """Action for the switch's toggled signal."""
            self.changed.fire(option_key, widget.get_active())

        def to_bool(to_convert):
            """Convert values to booleans in a way that won't decide that
            the string 'False' is True!"""
            if to_convert is None:
                return None
            elif isinstance(to_convert, str):
                text = to_convert.casefold().strip()
                if text == "true":
                    return True
                elif text == "false":
                    return False
                else:
                    return None
            else:
                return bool(to_convert)

        option_key = option["option"]

        active = to_bool(value) or to_bool(default) or False
        switch = Gtk.Switch(active=active, valign=Gtk.Align.CENTER)
        switch.connect("notify::active", on_notify_active)

        self.tooltip_default = _("Enabled") if default else _("Disabled")
        return self.build_option_widget(option, switch, expand=False)

    # SpinButton
    def _generate_range(self, option, value, default):
        """Generate a ranged spin button."""

        def on_changed(widget):
            """Action triggered on spin button 'changed' signal."""
            new_value = widget.get_value_as_int()
            self.changed.fire(option_key, new_value)

        option_key = option["option"]
        min_val = option["min"]
        max_val = option["max"]

        adjustment = Gtk.Adjustment(float(min_val), float(min_val), float(max_val), 1, 0, 0)
        spin_button = Gtk.SpinButton()
        spin_button.set_adjustment(adjustment)
        spin_button.set_value(value or default or 0)
        spin_button.connect("changed", on_changed)
        return self.build_option_widget(option, spin_button)

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
            self.changed.fire(option_key, option_value)

        option_key = option["option"]
        choices = option["choices"]
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

        expanded_choices, _tooltip_default = expand_combobox_choices()
        if value in [v for _k, v in expanded_choices]:
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
        combobox.set_valign(Gtk.Align.CENTER)
        return self.build_option_widget(option, combobox)

    # ComboBox
    def _generate_choice_with_entry(self, option, value, default):
        return self._generate_choice(option, value, default, has_entry=True)

    # ComboBox
    def _generate_choice_with_search(self, option, value, default):
        """Generate a searchable combo box"""

        def on_changed(_widget, new_value):
            self.changed.fire(option_key, new_value)

        option_key = option["option"]
        choice_func = option["choices"]
        combobox = SearchableCombobox(choice_func, value or default)
        combobox.connect("changed", on_changed)
        return self.build_option_widget(option, combobox)

    # FileChooserEntry
    def _generate_file(self, option, value, default, shell_quoting=False):
        """Generate a file chooser button to select a file."""

        def on_changed(entry):
            """Action triggered when the field's content changes."""
            text = entry.get_text()
            self.changed.fire(option_key, text)

        option_key = option["option"]
        warn_if_non_writable_parent = bool(option.get("warn_if_non_writable_parent"))

        if not value:
            value = default

        if "default_path" in option:
            lutris_config = LutrisConfig()
            chooser_default_path = lutris_config.system_config.get(option["default_path"])
        else:
            chooser_default_path = self.default_directory

        file_chooser = FileChooserEntry(
            title=_("Select file"),
            action=Gtk.FileChooserAction.OPEN,
            warn_if_non_writable_parent=warn_if_non_writable_parent,
            text=value,
            default_path=chooser_default_path,
            shell_quoting=shell_quoting,
        )

        if value:
            # If path is relative, complete with default directory
            if not os.path.isabs(value):
                value = os.path.expanduser(value)
                if not os.path.isabs(value):
                    value = os.path.join(self.default_directory, value)
            file_chooser.entry.set_text(value)

        file_chooser.set_valign(Gtk.Align.CENTER)
        file_chooser.connect("changed", on_changed)

        return self.build_option_widget(option, file_chooser)

    # FileChooserEntry
    def _generate_command_line(self, option, value, default):
        return self._generate_file(option, value, default, shell_quoting=True)

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
            dialog.set_current_folder(first_file_dir or self.default_directory)
            response = dialog.run()
            if response == Gtk.ResponseType.ACCEPT:
                for filename in dialog.get_filenames():
                    if filename not in files:
                        files_list_store.append([filename])
                        files.append(filename)
                self.changed.fire(option_key, files)
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
                    self.changed.fire(option_key, files)

        option_key = option["option"]
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
        return self.build_option_widget(option, vbox, no_label=True)

    # FileChooserEntry
    def _generate_directory(self, option, value, default):
        """Generate a file chooser button to select a directory."""

        def on_changed(entry):
            """Action triggered when the field's content changes."""
            text = entry.get_text()
            self.changed.fire(option_key, text)

        option_key = option["option"]
        warn_if_non_writable_parent = bool(option.get("warn_if_non_writable_parent"))

        if not value:
            value = default

        directory_chooser = FileChooserEntry(
            title=_("Select folder"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            warn_if_non_writable_parent=warn_if_non_writable_parent,
            text=value,
            default_path=self.default_directory if not value else None,
        )
        directory_chooser.connect("changed", on_changed)
        directory_chooser.set_valign(Gtk.Align.CENTER)
        return self.build_option_widget(option, directory_chooser)

    # EditableGrid
    def _generate_mapping(self, option, value, default):
        """Adds an editable grid widget"""

        def on_changed(widget):
            values = dict(widget.get_data())
            self.changed.fire(option_key, values)

        option_key = option["option"]
        value = value or default or {}
        try:
            value = list(value.items())
        except AttributeError:
            logger.error("Invalid value of type %s passed to grid widget: %s", type(value), value)
            value = {}

        grid = EditableGrid(value, columns=["Key", "Value"])
        grid.connect("changed", on_changed, option_key)
        return self.build_option_widget(option, grid)

    @staticmethod
    def on_query_tooltip(_widget, _x, _y, _keybmode, tooltip, text):  # pylint: disable=unused-argument
        """Prepare a custom tooltip with a fixed width"""
        label = Label(text)
        label.set_use_markup(True)
        label.set_max_width_chars(60)
        event_box = Gtk.EventBox()
        event_box.add(label)
        event_box.show_all()
        tooltip.set_custom(event_box)
        return True


class UnderslungMessageBox(Gtk.Box):
    """A box to display a message with an icon inside the configuration dialog."""

    def __init__(self, icon_name, margin_left=18, margin_right=18, margin_bottom=6):
        super().__init__(
            spacing=6,
            visible=False,
            margin_left=margin_left,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            no_show_all=True,
        )

        image = Gtk.Image(visible=True)
        image.set_from_icon_name(icon_name, Gtk.IconSize.DND)
        self.pack_start(image, False, False, 0)
        self.label = Gtk.Label(visible=True, xalign=0)
        self.label.set_line_wrap(True)
        self.pack_start(self.label, False, False, 0)

    def show_markup(self, markup) -> bool:
        """Displays the markup given, and shows this box. If markup is empty or None,
        this hides the box instead. Returns the new visibility."""
        visible = bool(markup)

        if markup:
            self.label.set_markup(str(markup))

        self.set_visible(visible)
        return visible


class ConfigMessageBox(UnderslungMessageBox):
    def __init__(self, message, option_key, icon_name, **kwargs):
        self.message = message
        self.option_key = option_key
        super().__init__(icon_name, **kwargs)

        if not callable(message):
            text = gtk_safe(message)

            if text:
                self.label.set_markup(str(text))

    def update_warning(self, config: LutrisConfig) -> bool:
        try:
            if callable(self.message):
                text = self.message(config, self.option_key)
            else:
                text = self.message
        except Exception as err:
            logger.exception("Unable to generate configuration warning: %s", err)
            text = gtk_safe(str(err))

        return self.show_markup(text)


class ConfigWarningBox(ConfigMessageBox):
    def __init__(self, warning, option_key):
        super().__init__(warning, option_key, icon_name="dialog-warning")


class ConfigErrorBox(ConfigMessageBox):
    def __init__(self, error, option_key, wrapper):
        super().__init__(error, option_key, icon_name="dialog-error")
        self.wrapper = wrapper

    def update_warning(self, config: LutrisConfig) -> bool:
        visible = super().update_warning(config)
        self.wrapper.set_sensitive(not visible)
        return visible
