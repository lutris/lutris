import json
from collections.abc import Callable
from enum import Enum
from gettext import gettext as _
from typing import Any, Type

from gi.repository import GObject, Gtk

from lutris.gui.config.runner_config_boxes import (
    BaseRunnerConfigBox,
    GameOptionsBox,
    RunnerGeneralBox,
    RunnerOptionsBox,
    SystemOptionsOverrideBox,
)
from lutris.gui.dialogs import ErrorDialog, SavableModelessDialog
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate
from lutris.gui.widgets.common import Label, VBox
from lutris.runners import inject_runners
from lutris.runners.json import SETTING_JSON_RUNNER_DIR, JsonRunner
from lutris.runners.model import ModelRunner
from lutris.runners.model_validator import validate, validate_runner_name
from lutris.runners.runner import Runner
from lutris.runners.yaml import SETTING_YAML_RUNNER_DIR, YamlRunner
from lutris.util.yaml import write_yaml_to_file


class RunnerConfigCreator:
    def __init__(
        self,
        label: str = "",
        tooltip: str = "",
        widget_class: Type[BaseRunnerConfigBox] | None = None,
        icon_name: str = "",
        from_dict_override: Callable[[BaseRunnerConfigBox, dict[str, Any]], bool] | None = None,
        to_dict_override: Callable[[BaseRunnerConfigBox, dict[str, Any]], bool] | None = None,
    ) -> None:
        self.label: str = label
        self.tooltip: str = tooltip
        self.icon_name: str = icon_name
        self.widget_class: Type[BaseRunnerConfigBox] | None = widget_class

        from_dict_functor: Callable[[BaseRunnerConfigBox, dict[str, Any]], bool] | None = None
        if from_dict_override:
            from_dict_functor = from_dict_override
        elif self.widget_class:
            # extract the from_dict callable from the base widget class
            from_dict_functor = self.widget_class.from_dict

        to_dict_functor: Callable[[BaseRunnerConfigBox, dict[str, Any]], bool] | None = None
        if to_dict_override:
            to_dict_functor = to_dict_override
        elif self.widget_class:
            # extract the to_dict callable to the base widget class
            to_dict_functor = self.widget_class.to_dict

        def to_dict_wrapper(output_dict: dict[str, Any], input_config_box: BaseRunnerConfigBox) -> bool:
            if to_dict_functor:
                return to_dict_functor(input_config_box, output_dict)
            return True

        def from_dict_wrapper(output_config_box: BaseRunnerConfigBox, input_dict: dict[str, Any]) -> bool:
            if from_dict_functor:
                return from_dict_functor(output_config_box, input_dict)
            return True

        self.to_dict: Callable[[dict[str, Any], BaseRunnerConfigBox], bool] = to_dict_wrapper
        self.from_dict: Callable[[BaseRunnerConfigBox, dict[str, Any]], bool] = from_dict_wrapper


RUNNER_CONFIG_SCHEMA = {
    "general": RunnerConfigCreator(
        label=_("General Settings"),
        tooltip=_("General settings for the runner"),
        widget_class=RunnerGeneralBox,
        icon_name="emblem-system-symbolic",
    ),
    "game_options": RunnerConfigCreator(
        label=_("Game Options"),
        tooltip=_("Specify the game options for the config"),
        widget_class=GameOptionsBox,
        icon_name="emblem-system-symbolic",
    ),
    "runner_options": RunnerConfigCreator(
        label=_("Runner Options"),
        tooltip=_("Specify the runner options for the config"),
        widget_class=RunnerOptionsBox,
        icon_name="emblem-system-symbolic",
    ),
    "system_options_override": RunnerConfigCreator(
        label=_("System Options Override"),
        tooltip=_("Overrides for the System Options panel in the runner configuration"),
        widget_class=SystemOptionsOverrideBox,
        icon_name="emblem-system-symbolic",
    ),
}


class CreateRunnerBox(VBox):
    """Box for creating a runner"""

    COL_SIDEBAR_BUTTON = 0

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        sidebar = Gtk.ListBox(visible=True)
        sidebar.connect("row-activated", self._on_sidebar_activated)

        self.stack = Gtk.Stack(visible=True)
        self.stack.set_vhomogeneous(False)
        self.stack.set_interpolate_size(True)

        toplevel_box = Gtk.HBox(visible=True)
        toplevel_box.pack_start(sidebar, False, False, 0)
        toplevel_box.add(self.stack)

        self.config_boxes: dict[str, BaseRunnerConfigBox] = {}
        for runner_field, config_creator in RUNNER_CONFIG_SCHEMA.items():
            if not callable(config_creator.widget_class):
                continue

            stack_id = f"{runner_field}-stack"
            self.config_boxes[runner_field] = config_creator.widget_class(dict_key=runner_field, visible=True)
            self.stack.add_named(self.config_boxes[runner_field], stack_id)
            sidebar.add(
                self._get_sidebar_button(
                    text=_(config_creator.label),
                    tooltip=config_creator.tooltip,
                    icon_name=config_creator.icon_name,
                )
            )

        self.pack_start(toplevel_box, True, True, 0)

    def to_dict(self) -> dict[str, Any]:
        """Populate the runner dict with the values from each runner config widget"""
        runner_dict: dict[Any, Any] = {}
        for runner_field, runner_schema in RUNNER_CONFIG_SCHEMA.items():
            runner_schema.to_dict(runner_dict, self.config_boxes[runner_field])

        return runner_dict

    def from_dict(self, runner_dict: dict[str, Any]) -> bool:
        """Update the widget values using the runner config dict"""
        loaded_no_errors = True
        for runner_field, runner_schema in RUNNER_CONFIG_SCHEMA.items():
            runner_box_widget = self.config_boxes.get(runner_field)
            if not runner_box_widget:
                continue
            if not runner_schema.from_dict(runner_box_widget, runner_dict):
                # Continue loading the other fields into the UI even if a previous field
                # has failed
                loaded_no_errors = False

        return loaded_no_errors

    def _on_sidebar_activated(self, _sidebar, row: Gtk.ListBoxRow) -> None:
        row_index = row.get_index()
        self.stack.set_visible_child(self.stack.get_children()[row_index])

    def _get_sidebar_button(self, text: str, tooltip: str, icon_name: str) -> Gtk.HBox:
        hbox = Gtk.HBox(visible=True)
        hbox.set_margin_top(12)
        hbox.set_margin_bottom(12)
        hbox.set_tooltip_text(tooltip)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        icon.show()
        hbox.pack_start(icon, False, False, 6)

        label = Gtk.Label(label=text, visible=True)
        label.set_yalign(0.5)
        hbox.pack_start(label, False, False, 0)
        return hbox


class RunnerConfigEditMode(Enum):
    CREATE = 0
    UPDATE = 1


class RunnerConfigFileFormats(str, Enum):
    JSON = "json"
    YAML = "yml"


class RunnerNameEntry(Gtk.Entry, Gtk.Editable):  # type:ignore[misc]
    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept alphanumeric and dashes
        Do not allow backslashes or forward slashes to prevent upward path traverseral
        """
        new_text = "".join([c for c in new_text if c.isalnum() or c == "-"])
        length = len(new_text)
        self.get_buffer().insert_text(position, new_text, length)
        return position + length


class EditRunnerConfigDialog(SavableModelessDialog, DialogInstallUIDelegate):  # type:ignore[misc]
    """Allow creation of a runner config JSON"""

    __gsignals__ = {"runner-saved": (GObject.SIGNAL_RUN_FIRST, None, (str,))}

    def __init__(
        self, parent: Gtk.Widget | None = None, edit_mode=RunnerConfigEditMode.CREATE, runner: Runner | None = None
    ):
        super().__init__(_("Create New Runner Config"), parent=parent)  # type:ignore[arg-type]

        label = Label(_("Runner File Prefix"))
        self._create_runner_box = CreateRunnerBox()

        self._runner_name_entry = RunnerNameEntry(visible=True)
        self._runner_name_entry.set_tooltip_text(
            _("The prefix used to name the runner file for the runner in the form of <runner-file-prefix>.(json|yml)")
        )
        self._runner_name_entry.connect("changed", self._on_runner_name_changed)

        runner_fileformat_box = self._get_runner_format_box()

        # Only allow editing the runner name when creating a new runner
        # Existing runners cannot have their runner name changed as the save location would change
        # Also prevent changing the file format type as well
        if edit_mode == RunnerConfigEditMode.UPDATE:
            if isinstance(runner, ModelRunner):
                self._runner_name_entry.set_sensitive(False)
                self._runner_name_entry.set_text(runner.name)
                self._create_runner_box.from_dict(runner.to_dict())
                self._runner_format_dropdown.set_active_id(
                    RunnerConfigFileFormats.JSON if isinstance(runner, JsonRunner) else RunnerConfigFileFormats.YAML
                )
                self._runner_format_dropdown.set_sensitive(False)

        self.save_button.set_sensitive(bool(self._runner_name_entry.get_text()))

        name_box = Gtk.Box(visible=True, spacing=12, margin_start=12, margin_end=12)
        name_box.pack_start(label, False, False, 0)
        name_box.pack_start(self._runner_name_entry, True, True, 0)

        self.get_content_area().pack_start(name_box, False, False, 0)
        self.get_content_area().pack_start(runner_fileformat_box, False, False, 0)
        self.get_content_area().pack_start(self._create_runner_box, True, True, 0)

        self.show_all()

    def _get_runner_format_box(self):
        box = Gtk.Box(visible=True, spacing=12, margin_start=12, margin_end=12)
        label = Label(_("Runner Format Type"))

        fileformat_liststore = Gtk.ListStore(str, str)
        for fileformat in RunnerConfigFileFormats:
            fileformat_liststore.append((fileformat.name, fileformat.value))

        self._runner_format_dropdown = Gtk.ComboBox.new_with_model(fileformat_liststore)
        self._runner_format_dropdown.set_tooltip_text(_("The file format to used when saving the runner"))
        self._runner_format_dropdown.connect("changed", self._on_runner_name_changed)
        self._runner_format_dropdown.set_id_column(1)  # Contains the widget_type key used to create UI elements
        self._runner_format_dropdown.set_active_id(RunnerConfigFileFormats.YAML)

        cell = Gtk.CellRendererText()
        self._runner_format_dropdown.pack_start(cell, True)
        self._runner_format_dropdown.add_attribute(cell, "text", 0)
        box.pack_start(label, False, False, 0)
        box.pack_start(self._runner_format_dropdown, True, True, 0)

        return box

    def _on_runner_name_changed(self, widget):
        self.save_button.set_sensitive(bool(self._runner_name_entry.get_text()))

    def _inject_runner(self, runner_config_path):
        runner_name = self._runner_name_entry.get_text()

        runner_format = self._runner_format_dropdown.get_active_id()
        if runner_format == RunnerConfigFileFormats.JSON:
            new_runner = type(runner_name, (JsonRunner,), {"json_path": runner_config_path})
        else:
            new_runner = type(runner_name, (YamlRunner,), {"yaml_path": runner_config_path})
        inject_runners(runners={runner_name: new_runner})
        return new_runner

    def on_save(self, _widget):
        runner_dict = self._create_runner_box.to_dict()
        runner_name = self._runner_name_entry.get_text()
        runner_format = self._runner_format_dropdown.get_active_id()

        validate_result = validate(runner_dict)
        if validate_result.get_errors():
            error_string = "\n".join([f"{error.key_path}: {error.message}" for error in validate_result.get_errors()])
            ErrorDialog(
                error=_("Cannot save new runner '%s'\n%s") % (runner_name, error_string),
                parent=self,
            )
            return

        runner_name_validate_result = validate_runner_name(runner_name)
        if runner_name_validate_result.get_errors():
            error_string = "\n".join(
                [f"{error.key_path}: {error.message}" for error in runner_name_validate_result.get_errors()]
            )
            ErrorDialog(
                error=_("Cannot save new runner '%s'\n%s") % (runner_name, error_string),
                parent=self,
            )
            return

        if runner_format == RunnerConfigFileFormats.JSON:
            runner_config_path = (SETTING_JSON_RUNNER_DIR / f"{runner_name}.{runner_format}").resolve()
            if not runner_config_path.is_relative_to(SETTING_JSON_RUNNER_DIR):
                ErrorDialog(
                    error=_(
                        "Cannot save new runner '%s' to path '%s'\n"
                        "Runner name cannot contain '.' and the path must be relative to '%s'"
                    )
                    % (runner_name, runner_config_path, SETTING_JSON_RUNNER_DIR),
                    parent=self,
                )
                return

        elif runner_format == RunnerConfigFileFormats.YAML:
            runner_config_path = (SETTING_YAML_RUNNER_DIR / f"{runner_name}.{runner_format}").resolve()
            if not runner_config_path.is_relative_to(SETTING_YAML_RUNNER_DIR):
                ErrorDialog(
                    error=_(
                        "Cannot save new runner '%s' to path '%s'\n"
                        "Runner name cannot contain '.' and the path must be relative to '%s'"
                        % (runner_name, runner_config_path, SETTING_YAML_RUNNER_DIR)
                    ),
                    parent=self,
                )
                return

        if runner_format == RunnerConfigFileFormats.JSON:
            # Make json directory runner directory if it doesn't exist
            SETTING_JSON_RUNNER_DIR.mkdir(parents=True, exist_ok=True)
            runner_config_path = SETTING_JSON_RUNNER_DIR / f"{runner_name}.{runner_format}"
            with runner_config_path.open("w", encoding="utf-8") as runner_file:
                json.dump(runner_dict, runner_file, indent=4)
                runner_file.write("\n")
        elif runner_format == RunnerConfigFileFormats.YAML:
            SETTING_YAML_RUNNER_DIR.mkdir(parents=True, exist_ok=True)
            runner_config_path = SETTING_YAML_RUNNER_DIR / f"{runner_name}.{runner_format}"
            write_yaml_to_file(config=runner_dict, filepath=str(runner_config_path))

        # Injects the runner into the list of addon runners
        if self._inject_runner(runner_config_path):
            self.emit("runner-saved", runner_name)

        self.destroy()
