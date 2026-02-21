from abc import abstractmethod
from gettext import gettext as _
from sys import float_info
from typing import Any, Dict, Iterable, List, Optional

from gi.repository import Gdk, Gio, GObject, Gtk
from typing_extensions import override

from lutris.gui.widgets.common import EditableGrid, Label, VBox
from lutris.runners.model import DEFAULT_ENTRY_POINT_OPTION

WIDGET_TYPES = {
    "label": "UI label",
    "string": "Text Field",
    "bool": "Radio Button",
    "range": "Spin Box",
    "choice": "Combo Box",
    "choice_with_entry": "Combo Box with text entry",
    "choice_with_search": "Combo Box with filtering",
    "file": "File Chooser with Text Entry",
    "multiple_file": "Multi File Chooser",
    "directory": "Directory Chooser",
    "mapping": "Editible Grid (Key -> Value map)",
    "command_line": "File Chooser with text entry and shell quoting ",
}
CHOICE_WIDGET_TYPES = {"choice", "choice_with_entry", "choice_with_search"}
RANGE_WIDGET_TYPES = {
    "range",
}
FILE_CHOOSER_WIDGET_TYPES = {"file", "multiple_file", "command_line"}
DEFAULT_WIDGET_TYPE = "string"

ICON_NAME_STATE_LIST = [("changes-prevent-symbolic", False), ("changes-allow-symbolic", True)]


class IconToggleButton(Gtk.Button):
    """
    Button that swaps between multiple icons when clicked
    """

    __gsignals__ = {"index-changed": (GObject.SIGNAL_RUN_FIRST, None, (bool,))}

    def __init__(self, icon_name_states=ICON_NAME_STATE_LIST, init_index=0, **kwargs):
        super().__init__(**kwargs)
        self._icon_name_states = icon_name_states
        self._index = init_index % len(self._icon_name_states)

        self._image = Gtk.Image.new_from_icon_name(self._icon_name_states[self._index][0], Gtk.IconSize.BUTTON)
        self.set_image(self._image)

        def increment_index(button):
            self.index = (self._index + 1) % len(self._icon_name_states)

        self.connect("clicked", increment_index)

        self.set_tooltip_text(_("If locked, this field will not be saved to option object when writing the JSON file"))

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, value):
        self._index = value
        self._image.set_from_icon_name(self._icon_name_states[self._index][0], Gtk.IconSize.BUTTON)
        self.emit("index-changed", self._icon_name_states[self._index][1])

    def get_active(self) -> bool:
        return self._icon_name_states[self._index][1]


class BaseRunnerConfigBox(VBox):
    __gsignals__ = {"changed": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def to_dict(self):
        """Serialize Box fields to dict for use with saving to a file"""
        raise NotImplementedError()

    @abstractmethod
    def from_dict(self, value: Any):
        """Read Box fields from dict for use with loading config settings"""
        raise NotImplementedError()


class OptionBox(BaseRunnerConfigBox):
    DEFAULT_ADVANCED_STATE = False
    DEFAULT_VISIBLE_STATE = True
    DEFAULT_WARN_IF_NON_WRITABLE_PARENT = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_margin_top(0)

        self._option_entry = Gtk.Entry()
        self._option_box = self._get_option_box()

        self._type_id = ""
        self._type_dropdown: Gtk.ComboBox = Gtk.ComboBox.new_with_model(self._get_type_liststore())
        self._type_box = self._get_type_box()

        self._section_entry = Gtk.Entry()
        self._section_box = self._get_section_box()

        self._label_entry = Gtk.Entry()
        self._label_box = self._get_label_box()

        self._argument_entry = Gtk.Entry()
        self._argument_box = self._get_argument_box()

        self._help_entry = Gtk.Entry()
        self._help_box = self._get_help_box()

        self._default_entry: Gtk.Entry | Gtk.Switch = Gtk.Entry()
        self._default_box = self._get_default_box()

        self._advanced_enabled_button = IconToggleButton()
        self._advanced_entry = Gtk.Switch(active=OptionBox.DEFAULT_ADVANCED_STATE, valign=Gtk.Align.CENTER)
        self._advanced_entry.set_sensitive(False)
        self._advanced_box = self._get_advanced_box()

        self._choice_grid = EditableGrid(data={}, columns=["Key", "Value"])
        self._choices_box = self._get_choices_box()

        self._min_entry = Gtk.SpinButton()
        self._min_box = self._get_min_box()

        self._max_entry = Gtk.SpinButton()
        self._max_box = self._get_max_box()

        self._visible_enabled_button = IconToggleButton()
        self._visible_entry = Gtk.Switch(active=OptionBox.DEFAULT_VISIBLE_STATE, valign=Gtk.Align.CENTER)
        self._visible_entry.set_sensitive(False)
        self._visible_box = self._get_visible_box()

        self._default_path_entry = Gtk.Entry()
        self._default_path_box = self._get_default_path_box()

        self._conditional_on_entry = Gtk.Entry()
        self._conditional_on_box = self._get_conditional_on_box()

        self._visible_enabled_button = IconToggleButton()
        self._warn_if_non_writable_parent_enabled_button = IconToggleButton()
        self._warn_if_non_writable_parent_entry = Gtk.Switch(
            active=OptionBox.DEFAULT_WARN_IF_NON_WRITABLE_PARENT, valign=Gtk.Align.CENTER
        )
        self._warn_if_non_writable_parent_entry.set_sensitive(False)
        self._warn_if_non_writable_parent_box = self._get_warn_if_non_writable_parent_box()

        self.pack_start(self._option_box, False, False, 6)
        self.pack_start(self._label_box, False, False, 6)
        self.pack_start(self._section_box, False, False, 6)
        self.pack_start(self._argument_box, False, False, 6)
        self.pack_start(self._help_box, False, False, 6)
        self.pack_start(self._type_box, False, False, 6)
        self.pack_start(self._default_box, False, False, 6)
        self.pack_start(self._choices_box, False, False, 6)
        self.pack_start(self._min_box, False, False, 6)
        self.pack_start(self._max_box, False, False, 6)
        self.pack_start(self._advanced_box, False, False, 6)
        self.pack_start(self._visible_box, False, False, 6)
        self.pack_start(self._default_path_box, False, False, 6)
        self.pack_start(self._conditional_on_box, False, False, 6)
        self.pack_start(self._warn_if_non_writable_parent_box, False, False, 6)

        self._option_box.show_all()
        self.show_all()
        self.update_widgets()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the contents of the widget to a dictionary for serialization"""
        output_dict: Dict[str, Any] = {}
        if option := self._option_entry.get_text():
            output_dict["option"] = option
        if type_val := self._type_dropdown.get_active_id():
            output_dict["type"] = type_val
        if section := self._section_entry.get_text():
            output_dict["section"] = section
        if label := self._label_entry.get_text():
            output_dict["label"] = label
        if argument := self._argument_entry.get_text():
            output_dict["argument"] = argument
        if help_val := self._help_entry.get_text():
            output_dict["help"] = help_val

        default = self._default_entry
        if isinstance(default, Gtk.Entry):
            output_dict["default"] = default.get_text()
        elif isinstance(default, Gtk.Switch):
            output_dict["default"] = default.get_active()

        # Editable Grid should return a list of tuples of size 2
        if (choices := self._choice_grid.get_data()) and self._type_dropdown.get_active_id() in CHOICE_WIDGET_TYPES:
            output_dict["choices"] = [{choice[0]: choice[1]} for choice in choices]

        # Serialize the "advanced" value if either the enabled button is active
        # or the state is different than the default
        if (
            self._advanced_enabled_button.get_active()
            or self._advanced_entry.get_active() != OptionBox.DEFAULT_ADVANCED_STATE
        ):
            output_dict["advanced"] = self._advanced_entry.get_active()

        if (min_val := self._min_entry.get_value()) and self._type_dropdown.get_active_id() in RANGE_WIDGET_TYPES:
            output_dict["min"] = float(min_val)

        if (max_val := self._max_entry.get_text()) and self._type_dropdown.get_active_id() in RANGE_WIDGET_TYPES:
            output_dict["max"] = float(max_val)

        # Serialize the "visible" value if either the enabled button is active
        # or the state is different than the default
        if (
            self._visible_enabled_button.get_active()
            or self._visible_entry.get_active() != OptionBox.DEFAULT_VISIBLE_STATE
        ):
            output_dict["visible"] = self._visible_entry.get_active()

        if (
            default_path := self._default_path_entry.get_text()
        ) and self._type_dropdown.get_active_id() in FILE_CHOOSER_WIDGET_TYPES:
            output_dict["default_path"] = default_path

        if conditional_on := self._conditional_on_entry.get_text():
            output_dict["conditional_on"] = conditional_on

        # Serialize the "warn if parent directory is not writable" value if either the enabled button is active
        # or the state is different than the default
        if (
            self._warn_if_non_writable_parent_enabled_button.get_active()
            or self._warn_if_non_writable_parent_entry.get_active() != OptionBox.DEFAULT_WARN_IF_NON_WRITABLE_PARENT
        ):
            output_dict["warn_if_non_writable_parent"] = self._warn_if_non_writable_parent_entry.get_active()

        return output_dict

    def from_dict(self, option_dict: Optional[Dict[str, Any]]) -> bool:
        if not option_dict:
            return False

        """Populate widget entries from dictionary"""
        self._option_entry.set_text(option_dict.get("option", ""))
        self._type_dropdown.set_active_id(option_dict.get("type", DEFAULT_WIDGET_TYPE))
        self._section_entry.set_text(option_dict.get("section", ""))
        self._label_entry.set_text(option_dict.get("label", ""))
        self._argument_entry.set_text(option_dict.get("argument", ""))
        self._help_entry.set_text(option_dict.get("help", ""))

        default = option_dict.get("default", "")
        if isinstance(self._default_entry, Gtk.Entry):
            self._default_entry.set_text(default)
        elif isinstance(self._default_entry, Gtk.Switch):
            self._default_entry.set_active(default)

        self._advanced_entry.set_active(option_dict.get("advanced", False))

        self._choice_grid.liststore.clear()
        choices = option_dict.get("choices", [])
        if isinstance(choices, Iterable):
            for choice in choices:
                # Add each choice array element that has at least 2 entries
                if isinstance(choice, dict):
                    for key, value in choice.items():
                        self._choice_grid.liststore.append((key, value))
                elif isinstance(choice, list) and len(choice) == 2:
                    self._choice_grid.liststore.append(choice)

        self._min_entry.set_text(str(option_dict.get("min", "")))
        self._max_entry.set_text(str(option_dict.get("max", "")))
        self._visible_entry.set_active(option_dict.get("visible", True))
        self._default_path_entry.set_text(option_dict.get("default_path", ""))
        self._conditional_on_entry.set_text(option_dict.get("conditional_on", ""))

        if "warn_if_non_writable_parent" in option_dict:
            self._warn_if_non_writable_parent_enabled_button.index = 1
            self._warn_if_non_writable_parent_entry.set_active(option_dict["warn_if_non_writable_parent"])
        else:
            # disable the warn if non writable parent field if the dictionary doesn't have the key at all
            self._warn_if_non_writable_parent_enabled_button.index = 0

        return True

    def update_widgets(self):
        """Update widget visibility when a change event occurs"""
        self._update_choices_visibility()
        self._update_range_visibility()
        self._update_default_path_visibility()

    def connect_option_name_changed(self, callable, *args):
        """Supply a callable to connect to the changed event of the Option field
        This can be used by an expander or label to update its text as the option is modified
        """
        self._option_entry.connect("changed", callable, *args)

    # "option" methods
    def _get_option_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Option"))
        box.pack_start(label, False, False, 0)

        self._option_entry.set_max_length(150)
        self._option_entry.set_tooltip_text(_("Name of option to set for field"))
        self._option_entry.connect("changed", self._on_option_changed)
        box.pack_start(self._option_entry, True, True, 0)
        return box

    def _on_option_changed(self, widget):
        self.emit("changed")

    # "type" methods
    def _get_type_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Type"))

        self._type_dropdown.set_id_column(1)  # Contains the widget_type key used to create UI elements
        self._type_dropdown.set_active_id(DEFAULT_WIDGET_TYPE)
        self._type_id = self._type_dropdown.get_active_id()
        self._type_dropdown.connect("changed", self._on_type_changed)

        cell = Gtk.CellRendererText()
        self._type_dropdown.pack_start(cell, True)
        self._type_dropdown.add_attribute(cell, "text", 0)
        box.pack_start(label, False, False, 0)
        box.pack_start(self._type_dropdown, True, True, 0)

        return box

    def _on_type_changed(self, widget: Gtk.ComboBox):
        """Action called when type drop down is changed."""
        new_type = widget.get_active_id()
        old_type = self._type_id
        self._update_default_box(new_type=new_type, old_type=old_type)
        self.update_widgets()
        self._type_id = new_type
        self.emit("changed")

    @staticmethod
    def _get_type_liststore():
        """Build a ListStore with available types."""
        type_liststore = Gtk.ListStore(str, str)
        type_liststore.append((_("Select a type for the option field"), ""))

        for widget_type, widget_desc in WIDGET_TYPES.items():
            type_liststore.append((f"{widget_type} ({widget_desc})", widget_type))
        return type_liststore

    # "section" methods
    def _get_section_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Section"))
        box.pack_start(label, False, False, 0)

        self._section_entry.set_max_length(150)
        self._section_entry.set_tooltip_text(_("Creates frame box around option if non-empty"))
        self._section_entry.connect("changed", self._on_section_changed)
        box.pack_start(self._section_entry, True, True, 0)
        return box

    def _on_section_changed(self, widget):
        self.emit("changed")

    # "label" methods
    def _get_label_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Label"))
        box.pack_start(label, False, False, 0)

        self._label_entry.set_max_length(150)
        self._label_entry.set_tooltip_text(_("Human readable label to for option"))
        self._label_entry.connect("changed", self._on_label_changed)
        box.pack_start(self._label_entry, True, True, 0)
        return box

    def _on_label_changed(self, widget):
        self.emit("changed")

    # "argument" methods
    def _get_argument_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Argument"))
        box.pack_start(label, False, False, 0)

        self._argument_entry.set_max_length(150)
        self._argument_entry.set_tooltip_text(
            _("Argument key provided with launching the game when option has a value")
        )
        self._argument_entry.connect("changed", self._on_argument_changed)
        box.pack_start(self._argument_entry, True, True, 0)
        return box

    def _on_argument_changed(self, widget):
        self.emit("changed")

    # "help" methods
    def _get_help_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Help"))
        box.pack_start(label, False, False, 0)

        self._help_entry.set_max_length(150)
        self._help_entry.set_tooltip_text(_("Help text provided when hovering above the option"))
        self._help_entry.connect("changed", self._on_help_changed)
        box.pack_start(self._help_entry, True, True, 0)
        return box

    def _on_help_changed(self, widget):
        self.emit("changed")

    # "default" methods
    def _get_default_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Default"))
        self._default_entry.set_tooltip_text(_("Default value for this option"))
        self._default_entry.connect("changed", self._on_default_changed)
        box.pack_start(label, False, False, 0)
        box.pack_start(self._default_entry, True, True, 0)

        return box

    def _update_default_box(self, new_type, old_type):
        if new_type == old_type:
            return

        if new_type == "bool":
            if not isinstance(self._default_entry, Gtk.Switch):
                if self._default_entry:
                    self._default_entry.destroy()
                self._default_entry = Gtk.Switch(active=False, valign=Gtk.Align.CENTER, visible=True)
                self._default_entry.set_tooltip_text(_("Default value for this option"))
                self._default_entry.connect("notify::active", self._on_default_changed)
                self._default_box.pack_start(
                    self._default_entry, False, False, 0
                )  # Don't expand Switch button for styling
        else:
            if not isinstance(self._default_entry, Gtk.Entry):
                if self._default_entry:
                    self._default_entry.destroy()
                self._default_entry = Gtk.Entry(visible=True)
                self._default_entry.set_max_length(150)
                self._default_entry.set_tooltip_text(_("Default value for this option"))
                self._default_entry.connect("changed", self._on_default_changed)
                self._default_box.pack_start(self._default_entry, True, True, 0)  # Expand text entry for usability

    def _on_default_changed(self, widget, gparam=None):
        self.emit("changed")

    # "Advanced" methods
    def _get_advanced_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Advanced"))

        self._advanced_entry.connect("notify::active", self._on_advanced_changed)
        self._advanced_entry.set_tooltip_text(_("If set, the option is only shown when the Advanced setting is active"))

        def toggle_sensitivity(widget, state):
            self._advanced_entry.set_sensitive(state)

        # toggle sensitivity of widget when the enabled button selected index changes
        self._advanced_enabled_button.connect("index-changed", toggle_sensitivity)
        box.pack_start(label, False, False, 0)
        box.pack_start(self._advanced_entry, False, False, 0)
        box.pack_end(self._advanced_enabled_button, False, False, 0)
        return box

    def _on_advanced_changed(self, switch, gparam):
        self.emit("changed")

    # "choices" methods
    def _get_choices_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Choices"))

        # Add placeholder text for the key value columns
        for treeview_column in self._choice_grid.treeview.get_columns():
            for cell_renderer in treeview_column.get_cells():
                cell_renderer.set_property("placeholder-text", (_("<blank>")))
        self._choice_grid.connect("changed", self._on_choices_changed)

        box.pack_start(label, False, False, 0)
        box.pack_start(self._choice_grid, True, True, 0)  # expand but don't fill to keep the buttons proportioned

        return box

    def _update_choices_visibility(self):
        if not (self._choices_box and self._type_dropdown):
            return

        if self._type_dropdown.get_active_id() in CHOICE_WIDGET_TYPES:
            self._choices_box.set_visible(True)
            self._choices_box.set_no_show_all(False)
        else:
            self._choices_box.set_visible(False)
            self._choices_box.set_no_show_all(True)

    def _on_choices_changed(self, widget):
        self.emit("changed")

    # "min" methods
    def _get_min_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Min"))
        box.pack_start(label, False, False, 0)

        adjustment = Gtk.Adjustment(0.0, -float_info.max, float_info.max, 1, 0, 0)
        self._min_entry.set_adjustment(adjustment)
        self._min_entry.set_tooltip_text(
            _("Set minimum value for a Spin Box. Only applicable when the option type is 'range'")
        )
        self._min_entry.connect("changed", self._on_min_changed)
        box.pack_start(self._min_entry, True, True, 0)
        return box

    def _on_min_changed(self, widget):
        self.emit("changed")

    # "max" methods
    def _get_max_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Max"))
        box.pack_start(label, False, False, 0)

        adjustment = Gtk.Adjustment(0.0, -float_info.max, float_info.max, 1, 0, 0)
        self._max_entry.set_adjustment(adjustment)
        self._max_entry.set_tooltip_text(
            _("Set maximum value for a Spin Box. Only applicable when the option type is 'range'")
        )
        self._max_entry.connect("changed", self._on_max_changed)
        box.pack_start(self._max_entry, True, True, 0)
        return box

    def _on_max_changed(self, widget):
        self.emit("changed")

    # "range" methods
    # combines min and max fields
    def _update_range_visibility(self):
        if not (self._min_box and self._max_box and self._type_dropdown):
            return

        if self._type_dropdown.get_active_id() in RANGE_WIDGET_TYPES:
            self._min_box.set_visible(True)
            self._min_box.set_no_show_all(False)
            self._max_box.set_visible(True)
            self._max_box.set_no_show_all(False)
        else:
            self._min_box.set_visible(False)
            self._min_box.set_no_show_all(True)
            self._max_box.set_visible(False)
            self._max_box.set_no_show_all(True)

    # "visible" methods
    def _get_visible_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Visible"))

        self._visible_entry.connect("notify::active", self._on_visible_changed)
        self._visible_entry.set_tooltip_text(_("When set to false option will not appear in UI"))

        def toggle_sensitivity(widget, state):
            self._visible_entry.set_sensitive(state)

        # toggle sensitivity of widget when the enabled button selected index changes
        self._visible_enabled_button.connect("index-changed", toggle_sensitivity)
        box.pack_start(label, False, False, 0)
        box.pack_start(self._visible_entry, False, False, 0)
        box.pack_end(self._visible_enabled_button, False, False, 0)
        return box

    def _on_visible_changed(self, switch, gparam):
        self.emit("changed")

    # "default_path" methods
    def _get_default_path_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Default Path"))
        box.pack_start(label, False, False, 0)

        self._default_path_entry.set_text("game_path")
        self._default_path_entry.set_tooltip_text(_("Set the default file path to use when opening the File Chooser"))
        self._default_path_entry.connect("changed", self._on_default_path_changed)
        box.pack_start(self._default_path_entry, True, True, 0)
        return box

    def _on_default_path_changed(self, widget):
        self.emit("changed")

    def _update_default_path_visibility(self):
        if not (self._default_path_box and self._type_dropdown):
            return

        if self._type_dropdown.get_active_id() in FILE_CHOOSER_WIDGET_TYPES:
            self._default_path_box.set_visible(True)
            self._default_path_box.set_no_show_all(False)
        else:
            self._default_path_box.set_visible(False)
            self._default_path_box.set_no_show_all(True)

    # "conditional_on" methods
    def _get_conditional_on_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Conditional On"))
        box.pack_start(label, False, False, 0)

        self._conditional_on_entry.set_max_length(150)
        self._conditional_on_entry.set_tooltip_text(
            _(
                "Enables this control based on the boolean value of the referenced option in this field."
                " If the referenced option doesn't exist, the control will be disabled"
            )
        )
        self._conditional_on_entry.connect("changed", self._on_conditional_on_changed)
        box.pack_start(self._conditional_on_entry, True, True, 0)
        return box

    def _on_conditional_on_changed(self, widget):
        self.emit("changed")

    # "Warn if non writable parent" methods
    def _get_warn_if_non_writable_parent_box(self):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_("Warn if non-writable parent"))

        self._warn_if_non_writable_parent_entry.connect("notify::active", self._on_warn_if_non_writable_parent_changed)
        self._warn_if_non_writable_parent_entry.set_tooltip_text(
            _("Triggers a warning if the parent directory for a File Chooser option is not writable")
        )

        def toggle_sensitivity(widget, state):
            self._warn_if_non_writable_parent_entry.set_sensitive(state)

        # toggle sensitivity of widget when the enabled button selected index changes
        self._warn_if_non_writable_parent_enabled_button.connect("index-changed", toggle_sensitivity)

        box.pack_start(label, False, False, 0)
        box.pack_start(self._warn_if_non_writable_parent_entry, False, False, 0)
        box.pack_end(self._warn_if_non_writable_parent_enabled_button, False, False, 0)
        return box

    def _on_warn_if_non_writable_parent_changed(self, switch, gparam):
        self.emit("changed")


class BaseConfigListBox(BaseRunnerConfigBox):
    def __init__(self, data, derived_widget_type: type[OptionBox]):
        super().__init__()

        self._widget_type = derived_widget_type

        self._buttons = []
        self._add_button = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        self._add_button.set_visible(True)
        self._buttons.append(self._add_button)
        self._add_button.connect("clicked", self._on_add)

        self._list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)

        scrollable_window = Gtk.ScrolledWindow(visible=True)
        scrollable_window.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scrollable_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollable_window.set_size_request(400, -1)
        scrollable_window.add(self._list_box)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=True)
        for button in self._buttons:
            button_box.pack_start(button, False, False, 0)
        self.pack_start(button_box, False, False, 0)
        self.pack_start(scrollable_window, True, True, 0)

        self._remove_widget = None
        action_id = "remove"
        remove_action = Gio.SimpleAction.new(name=action_id)
        remove_action.connect("activate", self._on_delete_row)
        option_action_group = Gio.SimpleActionGroup()
        option_action_group.insert(remove_action)
        self.insert_action_group("option", option_action_group)

        menu = Gio.Menu()
        menu.append(_("Remove"), f"option.{action_id}")
        self._popup_menu = Gtk.Popover.new_from_model(relative_to=None, model=menu)

        self.show_all()

    def to_dict(self) -> List[Any]:
        """Convert the contents of the widget to a list for serialization"""

        # Hierarchy layout for the list box is as follows
        # <list box>
        #   <list_row 1>
        #     <hbox>
        #       <delete button/>
        #       <event_box>
        #         <expander>
        #           <option widget>
        #   <list_row 2>
        #   ...
        #   <list_row N>
        output_list = []
        for list_box_row in self._list_box.get_children():
            hbox = list_box_row.get_children()[0]  # type: ignore
            event_box = hbox.get_children()[1]
            expander = event_box.get_children()[0]
            option_widget = expander.get_children()[0]
            output_list.append(option_widget.to_dict())

        return output_list

    def from_dict(self, values: Optional[List[Any]]) -> bool:
        """Populate widget entry from list"""
        if values is None:
            return False

        # Clear out any existing row widgets from the list before populating
        self._list_box.foreach(lambda row: self._list_box.remove(row))

        for value in values:
            option_widget = self._widget_type()
            if option_widget.from_dict(value):
                self.add_widget(option_widget)

        return True

    def add_widget(self, new_widget: OptionBox) -> Gtk.Expander:
        """Adds the widget as a new row in the list box
        A newly created expander which wraps the new widget is returned
        """

        expander = Gtk.Expander(visible=True)
        expander.set_expanded(True)

        delete_button = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
        delete_button.set_visible(True)

        list_box_row = Gtk.ListBoxRow(visible=True)
        delete_button.connect("clicked", self._on_delete, list_box_row)

        # Used to handle the button press-event for descendent widgets
        event_box = Gtk.EventBox(visible=True)
        event_box.connect("button-press-event", self._list_box_popup_menu, list_box_row)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=True)

        event_box.add(expander)
        expander.add(new_widget)
        hbox.pack_start(delete_button, False, False, 0)
        hbox.pack_start(event_box, True, True, 0)
        list_box_row.add(hbox)
        self._list_box.add(list_box_row)

        return expander

    def _on_add(self, widget):
        self.add_widget(self._widget_type())
        self.emit("changed")

    def _on_delete(self, widget, list_bow_row):
        if list_bow_row in self._list_box.get_children():
            self._list_box.remove(list_bow_row)
            self.emit("changed")

    def _list_box_popup_menu(self, widget, event: Gdk.EventButton, list_box_row):
        """Create popup menu that can be remove list box rows"""
        if event.button != Gdk.BUTTON_SECONDARY:
            return

        self._remove_widget = list_box_row

        click_rect = Gdk.Rectangle()
        click_rect.x = int(event.x)
        click_rect.y = int(event.y)
        self._popup_menu.set_relative_to(widget)
        self._popup_menu.set_pointing_to(click_rect)
        self._popup_menu.popup()

    def _on_delete_row(self, action, parameter):
        if self._remove_widget:
            list_box_row = self._remove_widget
            self._remove_widget = None
            self._on_delete(None, list_box_row)


class EditableOptionList(BaseConfigListBox):
    """Override of BaseConfigListBox which adds support for listening
    for the 'changed' signal of the UI element representing the "option" key
    The "option" key is the required key for game_option, runner_option, system_option elements
    """

    def add_widget(self, new_widget: OptionBox):
        expander = super().add_widget(new_widget)

        def on_option_name_changed(option_name_widget):
            expander.set_label(option_name_widget.get_text())

        new_widget.connect_option_name_changed(on_option_name_changed)


class GameOptionsBox(EditableOptionList):
    """Stores list of Game Options UI elements"""

    def __init__(self):
        super().__init__(data={}, derived_widget_type=OptionBox)

        # Add a row for the DEFAULT_ENTRY_POINT_OPTION on initialization of the game options.
        # The game options requires at an option that matches the "entry_point_option" field
        # so it is added to reduce the boilerplate user
        entry_point_widget = self._widget_type()
        self.add_widget(entry_point_widget)
        entry_point_widget._option_entry.set_text(DEFAULT_ENTRY_POINT_OPTION)
        entry_point_widget._type_dropdown.set_active_id("file")
        entry_point_widget._label_entry.set_text("ROM/ISO/exe file")


class RunnerOptionsBox(EditableOptionList):
    """Stores list of Runner Options UI elements"""

    def __init__(self):
        super().__init__(data={}, derived_widget_type=OptionBox)


class SystemOptionsOverrideBox(EditableOptionList):
    """Stores list of System Options Overrides"""

    def __init__(self):
        super().__init__(data={}, derived_widget_type=OptionBox)


class BaseConfigTextBox(BaseRunnerConfigBox):
    def __init__(self, label, tooltip="", **kwargs):
        super().__init__(**kwargs)
        self._text_entry = Gtk.Entry()
        self._text_box = self._get_text_box(label, tooltip)
        self.pack_start(self._text_box, False, False, 0)
        self.show_all()

    def _get_text_box(self, label, tooltip=""):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_(label))
        box.pack_start(label, False, False, 0)

        self._text_entry.set_max_length(500)
        self._text_entry.set_tooltip_text(_(tooltip))
        self._text_entry.connect("changed", self._on_text_changed)
        box.pack_start(self._text_entry, True, True, 0)
        return box

    def _on_text_changed(self, widget):
        self.emit("changed")

    def to_dict(self) -> str:
        """Convert the contents of the widget to a string for serialization"""
        output_string = ""
        if _text := self._text_entry.get_text():
            output_string = _text

        return output_string

    def from_dict(self, text_string: Optional[str]) -> bool:
        """Populate widget entry from string"""
        if text_string is None:
            return False
        self._text_entry.set_text(text_string)
        return True


class HumanNameBox(BaseConfigTextBox):
    def __init__(self, **kwargs):
        super().__init__(label=_("Human Name"), tooltip=_("Human readable name for the runner"), **kwargs)


class DescriptionBox(BaseConfigTextBox):
    def __init__(self, **kwargs):
        super().__init__(label=_("Description"), tooltip=("Description of the runner"), **kwargs)


class RunnerExecutableBox(BaseConfigTextBox):
    def __init__(self, **kwargs):
        super().__init__(label=_("Runner Executable"), tooltip=_("Path to the runner executable"), **kwargs)


class FlatpakIdBox(BaseConfigTextBox):
    def __init__(self, **kwargs):
        super().__init__(
            label=_("Flatpak ID"), tooltip=_("ID of flatpak app which can be used to install the runner"), **kwargs
        )


class DownloadUrlBox(BaseConfigTextBox):
    def __init__(self, **kwargs):
        super().__init__(label=_("Download URL"), tooltip=_("Url where runner can be downloaded by Lutris"), **kwargs)


class EntryPointOptionBox(BaseConfigTextBox):
    def __init__(self, **kwargs):
        super().__init__(
            label=_("Entry Point Option"),
            tooltip=_(
                "Name for the primary field in the 'game_options' that is passed to the runner arguments for execution"
            ),
            **kwargs,
        )
        self._text_entry.set_text(DEFAULT_ENTRY_POINT_OPTION)


class BaseConfigSwitchBox(BaseRunnerConfigBox):
    def __init__(self, label, tooltip="", initial_value=False, **kwargs):
        super().__init__(**kwargs)
        self._switch_entry = Gtk.Switch(active=initial_value)
        self._switch_box = self._get_switch_box(label, tooltip)
        self.pack_start(self._switch_box, False, False, 0)
        self.show_all()

    def _get_switch_box(self, label, tooltip=""):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_(label))
        box.pack_start(label, False, False, 0)

        self._switch_entry.set_tooltip_text(_(tooltip))
        self._switch_entry.connect("notify::active", self._on_switch_active)
        box.pack_start(self._switch_entry, False, False, 0)
        return box

    def _on_switch_active(self, widget):
        self.emit("changed")

    def to_dict(self) -> bool:
        """Convert the contents of the widget to a boolean for serialization"""
        return self._switch_entry.get_active()

    def from_dict(self, switch_state: Optional[bool]) -> bool:
        """Populate widget entries from a boolean"""
        if switch_state is None:
            return False
        self._switch_entry.set_active(switch_state)
        return True


class RunnableAloneBox(BaseConfigSwitchBox):
    def __init__(self, **kwargs):
        super().__init__(
            label=_("Runnable Alone"),
            tooltip=_("If set, the runner can be opened standalone in the sidebar"),
            initial_value=True,
            **kwargs,
        )


class BaseConfigGridBox(BaseRunnerConfigBox):
    def __init__(self, label, tooltip="", **kwargs):
        super().__init__(**kwargs)
        self._grid_entry = EditableGrid(data={}, columns=("key", "value"))
        self._grid_box = self._get_grid_box(label, tooltip)
        self.pack_start(self._grid_box, False, False, 0)
        self.show_all()

    def _get_grid_box(self, label, tooltip=""):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_right=12, margin_left=12)
        label = Label(_(label))
        box.pack_start(label, False, False, 0)

        self._grid_entry.set_tooltip_text(_(tooltip))
        for i, treeview_column in enumerate(self._grid_entry.treeview.get_columns()):
            for cell_renderer in treeview_column.get_cells():
                cell_renderer.set_property("placeholder-text", (_("<blank>")))
                cell_renderer.connect("edited", self._on_cell_edited, i)

        box.pack_start(self._grid_entry, True, True, 0)
        return box

    def _on_cell_edited(self, widget, path, _text, field):
        self.emit("changed")

    def to_dict(self) -> Dict[str, str]:
        """Convert the contents of the widget to a list of dict for serialization"""
        output_dict = {}
        if grid_rows := self._grid_entry.get_data():
            output_dict = dict(grid_rows)
        return output_dict

    def from_dict(self, grid_values: Optional[Dict[str, str] | List[str] | str]) -> bool:
        """Populate widget entry from dict"""
        if not isinstance(grid_values, Iterable):
            return False

        self._grid_entry.liststore.clear()
        if isinstance(grid_values, dict):
            for key, value in grid_values.items():
                self._grid_entry.liststore.append((key, value))
        elif isinstance(grid_values, list):
            for key in grid_values:
                self._grid_entry.liststore.append((key, key))
        else:
            key = str(grid_values)
            self._grid_entry.liststore.append((key, key))
        return True


class PlatformsBox(BaseConfigGridBox):
    def __init__(self, **kwargs):
        super().__init__(label=_("Platforms"), tooltip=_("Platforms supported by runner"), **kwargs)

    def _on_cell_edited(self, widget, path, _text, field):
        # Default the second column to the same as the first column if empty
        if field == 0 and not self._grid_entry.liststore[path][1]:
            self._grid_entry.liststore[path][1] = self._grid_entry.liststore[path][0].strip()
        super()._on_cell_edited(widget, path, _text, field)


class EnvBox(BaseConfigGridBox):
    def __init__(self, **kwargs):
        super().__init__(
            label=_("Environment Variables"), tooltip=_("Environment Variables to set when invoking runner"), **kwargs
        )


class BaseConfigComboBox(BaseRunnerConfigBox):
    def __init__(self, label, tooltip="", **kwargs):
        super().__init__(**kwargs)
        self._combo_dropdown = Gtk.ComboBox.new_with_model(self._get_combo_liststore())
        self._combo_box = self._get_combo_box(label, tooltip)
        self.pack_start(self._combo_box, False, False, 0)
        self.show_all()

    def _get_combo_box(self, label, tooltip):
        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12)
        label = Label(_(label))

        self._combo_dropdown.set_id_column(1)
        self._combo_dropdown.set_tooltip_text(_(tooltip))
        self._set_default_active_id()
        self._combo_dropdown.connect("changed", self._on_dropdown_changed)

        cell = Gtk.CellRendererText()
        self._combo_dropdown.pack_start(cell, True)
        self._combo_dropdown.add_attribute(cell, "text", 0)
        box.pack_start(label, False, False, 0)
        box.pack_start(self._combo_dropdown, True, True, 0)
        return box

    def _on_dropdown_changed(self, widget: Gtk.ComboBox):
        """Action called when combo dropdown is changed."""
        self.emit("changed")

    @staticmethod
    @abstractmethod
    def _get_combo_liststore():
        """Build a ListStore of string key to string value options for the combo box.
        Must be Overriden to allow Combo Box options to be available for widget
        """
        raise NotImplementedError()

    def _set_default_active_id(self):
        """Used to set the default entry for the  combo box.
        This is optional to override, if not then will default to index 0
        """
        self._combo_dropdown.set_active(0)

    def to_dict(self) -> str:
        """Convert the contents of the widget to a string for serialization"""
        output_string = ""
        if combo_val := self._combo_dropdown.get_active_id():
            output_string = combo_val

        return output_string

    def from_dict(self, text_string: Optional[str]) -> bool:
        """Populate widget entry from string if is an available option in the combo box"""
        if text_string is None:
            return False

        return self._combo_dropdown.set_active_id(text_string)


class WorkingDirectoryBox(BaseConfigComboBox):
    def __init__(self, **kwargs):
        super().__init__(
            label=_("Working Directory"),
            tooltip=(
                "Default working directory when launching runner.\n"
                'Only value supported at this time "runner"\n"runner" -> Set the working directory to the directory'
                "of the runner executable"
            ),
            **kwargs,
        )

    @staticmethod
    @override
    def _get_combo_liststore():
        """Adds an entry to select "runner" working directory value
        This allows a runner to use the directory containing the runner executable if not overridden.
        """
        combo_liststore = Gtk.ListStore(str, str)
        combo_liststore.append((_("Don't set the default working directory"), ""))
        combo_liststore.append((_("Use the runner executable directory as the default working directory"), "runner"))

        return combo_liststore
