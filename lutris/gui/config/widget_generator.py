"""Widget generators and their signal handlers"""

import os
from abc import ABC, abstractmethod
from gettext import gettext as _
from inspect import Parameter, signature
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from gi.repository import Gdk, Gtk  # type: ignore

from lutris.config import LutrisConfig
from lutris.gui.widgets import NotificationSource
from lutris.gui.widgets.common import EditableGrid, FileChooserEntry, Label
from lutris.gui.widgets.searchable_entrybox import SearchableEntrybox
from lutris.util.log import logger
from lutris.util.strings import gtk_safe

if TYPE_CHECKING:
    from lutris.gui.config.boxes import ConfigBox


class WidgetGenerator(ABC):
    """This class generates widgets for an options page. It even adds the widgets
    to a 'wrapper' you can supply and, if required, that wrapper goes into a container
    which also contains message boxes for errors and warnings.

    The specific inner widgets are generated according to an option dict.

    The generator also accumulates and tracks the wrappers and containers for future use,
    and can update their state via a call to update_widgets(). When doing this, various callables
    in the option dicts can be re-evaluated; you provide a set of 'callback_args' and 'callback_kwargs'
    that are passed along to these callbacks. These collbacks also take the identifier of the
    option, from the 'option' key of the option dict.

    'changed' is a NotificationSource for whenever the generated widget changes a value;
    the same 'changed' NotificationSource is shared by all the widgets this generator generates.

    You can only create new containers, not discard old ones, but you *can* regenerate the widget
    inside the wrapper as a way to force it to update.
    """

    GeneratorFunction = Callable[[Dict[str, Any], Any, Any], Optional[Gtk.Widget]]

    def __init__(self, parent: "ConfigBox", *callback_args, **callback_kwargs) -> None:
        self.parent = parent
        self.callback_args = callback_args
        self.callback_kwargs = callback_kwargs
        self.changed = NotificationSource()  # takes option_key, new_value
        self.changed.register(self.on_changed, priority=1000)
        self._default_directory: Optional[str] = None
        self._current_parent: Optional[Gtk.Box] = None
        self._current_section: Optional[str] = None

        # These are outputs set by generate_widget() or generate_container()
        # and they are reset on each call.
        self.wrapper: Optional[Gtk.Box] = None
        self.default_value = None
        self.tooltip_default: Optional[str] = None
        self.options: Dict[str, Dict[str, Any]] = {}
        self.option_widget: Optional[Gtk.Widget] = None
        self.option_container: Optional[Gtk.Widget] = None
        self.warning_messages: List[Gtk.Widget] = []

        # These accumulate results across all widgets
        self.wrappers: Dict[str, Gtk.Container] = {}
        self.section_frames: List[SectionFrame] = []
        self.option_containers: Dict[str, Gtk.Container] = {}

        self._generators: Dict[str, WidgetGenerator.GeneratorFunction] = {
            "label": self._generate_label,
            "string": self._generate_string,
            "bool": self._generate_bool,
            "range": self._generate_range,
            "choice": self._generate_choice,
            "choice_with_entry": self._generate_choice_with_entry,
            "choice_with_search": self._generate_choice_with_search,
            "file": self._generate_file,
            "multiple_file": self._generate_multiple_file,
            "directory": self._generate_directory,
            "mapping": self._generate_mapping,
            "command_line": self._generate_command_line,
        }

    def on_changed(self, option_key: str, new_value: Any) -> None:
        """Called when any value is changed; this is called later than ordinary
        handlers for the 'changed' notification, and by default just updates the
        widgets."""
        self.update_widgets()

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

    # Widget Construction

    def add_container(self, option: Dict[str, Any], wrapper: Optional[Gtk.Box] = None) -> Optional[Gtk.Widget]:
        """Generates the option's widget, wrapper and container, and adds the container to the parent;
        if the option uses 'section', then the container is actually placed inside a SectionFrame,
        or in the previous frame if it is for the same section."""
        option_container = self.generate_container(option, wrapper)

        if option_container and self.parent:
            # Switch to new section if required
            if not self._current_parent:
                self._current_parent = self.parent

            if option.get("section") != self._current_section:
                self._current_section = option.get("section")
                if self._current_section:
                    frame = SectionFrame(self._current_section, visible=True)
                    self.section_frames.append(frame)
                    self._current_parent = frame.vbox
                    self.parent.pack_start(frame, False, False, 0)
                else:
                    self._current_parent = self.parent

            self._current_parent.pack_start(option_container, False, False, 0)
        return option_container

    def generate_container(self, option: Dict[str, Any], wrapper: Optional[Gtk.Box] = None) -> Optional[Gtk.Widget]:
        """Creates the widget, wrapper, and container; this returns the container
        (or the wrapper if there's no container)."""
        option_widget = self.generate_widget(option, wrapper)
        if option_widget and self.wrapper:
            option_key = option["option"]
            option_container = self.create_option_container(option, self.wrapper)
            self.option_containers[option_key] = option_container
            option_container.show_all()

            option_container.lutris_option_key = option_key  # type:ignore[attr-defined]
            option_container.lutris_option_label = option["label"]  # type:ignore[attr-defined]
            option_container.lutris_option_helptext = option.get("help") or ""  # type:ignore[attr-defined]

            # Mark advanced option containers, to be hidden by checking for this
            option_container.lutris_advanced = bool(option.get("advanced"))  # type:ignore[attr-defined]
            option_container.lutris_option = option  # type:ignore[attr-defined]

            self.option_container = option_container
            return option_container
        else:
            return None

    def generate_widget(self, option: Dict[str, Any], wrapper: Optional[Gtk.Box] = None) -> Optional[Gtk.Widget]:
        """This creates a wrapper box and a label and widget within it according to the options dict
        given. The option widget itself, is returned, but this method also sets attributes on the
        generator. You get 'wrapper', 'default_value', 'tooltip_default' and 'option_widget' which restates
        the return value. This returns None if the entire option should be omitted."""
        option_key = option["option"]
        option_type = option["type"]
        default = self.get_default(option)
        value = self.get_setting(option_key, default)

        self.default_value = default
        self.tooltip_default = None
        self.option_widget = None
        self.option_container = None
        self.warning_messages.clear()
        self.wrappers.pop(option_key, None)

        # Record the options themselves before anything is generated
        self.options[option_key] = option

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

        self.wrappers[option_key] = self.wrapper
        self.option_widget = option_widget
        self.tooltip_default = self.tooltip_default or (default if isinstance(default, str) else None)

        if option_widget:
            option_widget.show_all()

        self.configure_wrapper_box(self.wrapper, option, value, default)
        self.configure_warning_messages(option)
        return option_widget

    def configure_wrapper_box(self, wrapper: Gtk.Widget, option: Dict[str, Any], value: Any, default: Any) -> None:
        """Configures the wrapper box after it is created; this sets its tooltip, sensitivity, and
        creates warning message boxes."""

        # Attach a tooltip to the wrapper
        tooltip = self.get_tooltip(option, value, default)
        if tooltip:
            wrapper.props.has_tooltip = True
            wrapper.connect("query-tooltip", self.on_query_tooltip, tooltip)

    def get_tooltip(self, option: Dict[str, Any], value: Any, default: Any):
        tooltip = option.get("help")
        if self.tooltip_default:
            tooltip = tooltip + "\n\n" if tooltip else ""
            tooltip += _("<b>Default</b>: ") + self.tooltip_default
        return tooltip

    def configure_warning_messages(self, option: Dict[str, Any]):
        # Add message boxes under the widget
        if "error" in option:
            self.warning_messages.append(ConfigErrorBox(option["error"]))

        if "warning" in option:
            self.warning_messages.append(ConfigWarningBox(option["warning"]))

    def create_wrapper_box(self, option: Dict[str, Any], value: Any, default: Any) -> Optional[Gtk.Box]:
        """This creates the wrapper, which becomes the 'wrapper' attribute and which build_option_widget()
        populates. Returns None if the option is not visible; in that case no widget is generated either."""

        available = self._evaluate_flag_option("available", option)

        if not available:
            # If not available, there's no wrapper, and no widget!
            return None

        return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin_bottom=6, visible=True)

    def create_option_container(self, option: Dict[str, Any], wrapper: Gtk.Container) -> Gtk.Container:
        """This creates a wrapper box around the widget wrapper, to support additional controls. The
        base implementation wraps 'wrapper' in a Box with the error and warning widgets; if
        there are none it just returns 'wrapper'."""

        if self.warning_messages:
            option_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
            option_container.pack_start(wrapper, False, False, 0)

            for widget in self.warning_messages:
                option_container.pack_start(widget, False, False, 0)

            return option_container
        else:
            return wrapper

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

    # Dynamic Widget Updates

    def update_widgets(self) -> None:
        """Call this to update the visibility, sensitivity and other properties of
        the widgets, wrappers and containers already generated."""

        for option_key, container in self.option_containers.items():
            if hasattr(container, "lutris_option"):
                option = container.lutris_option
                wrapper = self.wrappers[option_key]
                self.update_option_container(option, container, wrapper)

        for frame in self.section_frames:
            visible = frame.has_visible_children()
            frame.set_visible(visible)
            frame.set_no_show_all(not visible)

    def update_option_container(self, option, container: Gtk.Container, wrapper: Gtk.Container):
        """This method updates an option container and its wrapper; this re-evaluates the
        relevant options in case they contain callables and those callables return different
        results."""

        # Update messages in message boxes that support it
        for child in container.get_children():
            if hasattr(child, "update_message"):
                child.update_message(option, self)

        # Hide entire container if the option is not visible
        visible = self.get_visibility(option)
        container.set_visible(visible)
        container.set_no_show_all(not visible)

        # Grey out option if condition unmet, or if a second setting is False
        condition: bool = self.get_condition(option)
        wrapper.set_sensitive(condition)

    # Widget factories

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

        active = to_bool(value)
        if active is None:
            active = bool(to_bool(default))

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
            expanded, tooltip_default, _valid_choices = expand_combobox_choices()
            for choice in expanded:
                liststore.append(choice)

            if tooltip_default:
                self.tooltip_default = str(tooltip_default)

        def expand_combobox_choices():
            expanded = []
            tooltip_default = None
            valid = []
            has_value = False
            for choice in choices:
                if isinstance(choice, str):
                    choice = (choice, choice)
                elif isinstance(choice, dict):
                    choice = next(iter(choice.items()))
                if choice[1] == value:
                    has_value = True
                if choice[1] == default:
                    tooltip_default = choice[0]
                    choice = (_("%s (default)") % choice[0], choice[1])
                valid.append(choice[1])
                expanded.append(choice)
            if not has_value and value:
                expanded.insert(0, (value, value))
            return expanded, tooltip_default, valid

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
        choices = self._evaluate_option("choices", None, option)

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

        expanded_choices, _tooltip_default, valid_choices = expand_combobox_choices()
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

        def get_invalidity_error(key: str):
            v = self.get_setting(key, self.get_default(option))
            if v in valid_choices:
                return None

            return _("The setting '%s' is no longer available. You should select another choice.") % v

        if not has_entry and value not in valid_choices:
            self.warning_messages.append(ConfigWarningBox(get_invalidity_error))

        return self.build_option_widget(option, combobox)

    # ComboBox
    def _generate_choice_with_entry(self, option, value, default):
        return self._generate_choice(option, value, default, has_entry=True)

    # Searchable Entry
    def _generate_choice_with_search(self, option, value, default):
        """Generate a searchable combo box"""

        def on_changed(_widget, new_value):
            self.changed.fire(option_key, new_value)

        option_key = option["option"]
        choices = option["choices"]
        entrybox = SearchableEntrybox(choices, value or default)
        entrybox.connect("changed", on_changed)
        return self.build_option_widget(option, entrybox)

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
        button = Gtk.Button(label=_("Add Files"))
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
        files_treeview = Gtk.TreeView(model=files_list_store)
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
        grid.connect("changed", on_changed)
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

    # Option access

    @abstractmethod
    def get_setting(self, option_key: str, default: Any) -> Any:
        """Reads the current value for a specific setting; this method must be
        implemented by a subclass."""
        raise NotImplementedError()

    def get_default(self, option: Dict[str, Any]) -> Any:
        """Returns the default value from the option; if it is callable, this calls
        it to get the actual default."""
        return self._evaluate_option("default", default=None, option=option)

    def get_visibility(self, option: Dict[str, Any]) -> bool:
        """Extracts the 'visible' option; if the option is missing this returns
        True, and if it is callable this calls it. Subclasses can add further conditions."""
        return self._evaluate_flag_option("visible", option)

    def get_condition(self, option: Dict[str, Any]) -> bool:
        """Extracts the 'condition' option; but also the 'conditional_on' option, and if both
        are present, then if either indicates the control should be disabled this will be false.."""
        condition = self._evaluate_flag_option("condition", option)
        conditional_on = option.get("conditional_on")

        if conditional_on:
            conditional_on_default = self.get_default(self.options[conditional_on])
            if not self.get_setting(conditional_on, conditional_on_default):
                return False

        container = self.option_containers[option["option"]]

        for child in container.get_children():
            if hasattr(child, "blocks_sensitivity") and child.blocks_sensitivity:
                return False

        return condition

    def _evaluate_flag_option(self, key: str, option: Dict[str, Any]) -> bool:
        """Evaluates a flag option; if is None or missing this returns True, and if
        it is callable this calls it (as with _evaluate_option) and converts
        the result to a bool."""
        flag = self._evaluate_option(key, default=True, option=option)
        return bool(flag) if flag is not None else True

    def _evaluate_option(self, key: str, default: Any, option: Dict[str, Any]) -> Any:
        """Evaluates an option; if is missing, then function returns 'default', and
        if it is callable this calls it, passing the option key, generator's args and kwargs.

        The callable may take fewer arguments; if so, this will pass as many argments
        as it will take, even if that is none at all."""

        if key not in option:
            return default

        value = option[key]
        return self.evaluate_option_value(value, option=option)

    def evaluate_option_value(self, value: Any, option: Dict[str, Any]) -> Any:
        """Evaluates the 'value' given, if it is callable. If not, this method just
        returns the 'value'.

        The 'value' is called with the option-key and then all the callback arguments
        given to this generator's __init__. If the 'value' takes fewer arguments than
        this, trailing arguments are omitted."""
        if callable(value):
            sig = signature(value)
            argcount = len(sig.parameters)

            option_key = option["option"]
            argsneeded = 1 + len(self.callback_args)

            if argcount >= argsneeded:  # enough declared args?
                return value(option_key, *self.callback_args, **self.callback_kwargs)
            elif any(p.kind == Parameter.VAR_POSITIONAL for p in sig.parameters.values()):  # unlimited args via *args?
                return value(option_key, *self.callback_args, **self.callback_kwargs)
            elif argcount == 0:  # no args?
                return value(**self.callback_kwargs)
            else:  # any other number of args
                args = list(self.callback_args)
                args.insert(0, option_key)
                args = args[:argcount]
                return value(*args, **self.callback_kwargs)

        return value


class SectionFrame(Gtk.Frame):
    """A frame that is styled to have particular margins, and can have its frame hidden.
    This leaves the content but removes the margins and borders and all that, so it looks
    like the frame was never there."""

    def __init__(self, section, **kwargs):
        super().__init__(label=section, **kwargs)
        self.section = section
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        self.add(self.vbox)
        self.get_style_context().add_class("section-frame")

    def has_visible_children(self):
        return any(w for w in self.vbox.get_children() if w.get_visible())


class WidgetWarningMessageBox(Gtk.Box):
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


class ConfigMessageBox(WidgetWarningMessageBox):
    def __init__(self, message, icon_name, **kwargs):
        self.message = message
        super().__init__(icon_name, **kwargs)

        if not callable(message):
            text = gtk_safe(message)

            if text:
                self.label.set_markup(str(text))

    def update_message(self, option: Dict[str, Any], generator: WidgetGenerator) -> bool:
        try:
            text = generator.evaluate_option_value(self.message, option)
        except Exception as err:
            logger.exception("Unable to generate configuration warning: %s", err)
            text = gtk_safe(str(err))

        return self.show_markup(text)


class ConfigWarningBox(ConfigMessageBox):
    def __init__(self, warning):
        super().__init__(warning, icon_name="dialog-warning")


class ConfigErrorBox(ConfigMessageBox):
    def __init__(self, error):
        super().__init__(error, icon_name="dialog-error")

    @property
    def blocks_sensitivity(self):
        """Called to check if the wrapper should be made insensitive
        because of this error box."""
        return self.get_visible()
