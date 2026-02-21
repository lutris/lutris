import json
from enum import Enum
from gettext import gettext as _
from typing import Any, Dict, Optional, Type

from gi.repository import GObject, Gtk

from lutris.gui.config.game_common import GameDialogCommon
from lutris.gui.config.runner_config_boxes import (
    BaseRunnerConfigBox,
    DescriptionBox,
    DownloadUrlBox,
    EntryPointOptionBox,
    EnvBox,
    FlatpakIdBox,
    GameOptionsBox,
    HumanNameBox,
    PlatformsBox,
    RunnableAloneBox,
    RunnerExecutableBox,
    RunnerOptionsBox,
    SystemOptionsOverrideBox,
    WorkingDirectoryBox,
)
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.widgets.common import Label, VBox
from lutris.runners import inject_runners
from lutris.runners.json import SETTING_JSON_RUNNER_DIR, JsonRunner
from lutris.runners.model import ModelRunner
from lutris.runners.runner import Runner
from lutris.runners.yaml import SETTING_YAML_RUNNER_DIR, YamlRunner
from lutris.util.yaml import write_yaml_to_file


class RunnerConfigCreator:
    def __init__(self, label="", tooltip="", widget_class=None, icon_name="") -> None:
        self.label: str = label
        self.tooltip: str = tooltip
        self.widget_class: Optional[Type[Gtk.Box]] = widget_class
        self.icon_name: str = icon_name


RUNNER_CONFIG_SCHEMA = {
    "human_name": RunnerConfigCreator(
        label=_("Display Name"),
        tooltip=_("Human readable name for the runner"),
        widget_class=HumanNameBox,
        icon_name="insert-text-symbolic",
    ),
    "description": RunnerConfigCreator(
        label=_("Description"),
        tooltip=_("Desciption of the runner"),
        widget_class=DescriptionBox,
        icon_name="insert-text-symbolic",
    ),
    "platforms": RunnerConfigCreator(
        label=_("Platforms"),
        tooltip=_("List of platforms the runner may invoke"),
        widget_class=PlatformsBox,
        icon_name="list-add-symbolic",
    ),
    "runner_executable": RunnerConfigCreator(
        label=_("Runner Executable"),
        tooltip=_("Path to the runner executable"),
        widget_class=RunnerExecutableBox,
        icon_name="applications-game-symbolic",
    ),
    "runnable_alone": RunnerConfigCreator(
        label=_("Runnable Alone"),
        tooltip=_("If set, the runner can be opened standalone in the sidebar"),
        widget_class=RunnableAloneBox,
        icon_name="application-x-executable-symbolic",
    ),
    "flatpak_id": RunnerConfigCreator(
        label=_("Flatpak ID"),
        tooltip=_("ID of flatpak app which can be used to install the runner"),
        widget_class=FlatpakIdBox,
        icon_name="insert-text-symbolic",
    ),
    "download_url": RunnerConfigCreator(
        label=_("Download URL"),
        tooltip=_("Url where runner can be downloaded by Lutris"),
        widget_class=DownloadUrlBox,
        icon_name="insert-text-symbolic",
    ),
    "entry_point_option": RunnerConfigCreator(
        label=_("Entry Point Option"),
        tooltip=_(
            "Name for the primary field in the 'game_options' that is passed to the runner arguments for execution"
        ),
        widget_class=EntryPointOptionBox,
        icon_name="insert-text-symbolic",
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
    "env": RunnerConfigCreator(
        label=_("Environment Variables"),
        tooltip=_("Environment Variable to always set when launching runner"),
        widget_class=EnvBox,
        icon_name="list-add-symbolic",
    ),
    "working_dir": RunnerConfigCreator(
        label=_("Working Directory"),
        tooltip=_(
            'Default working directory when launching the runner. Supported value is "runner",'
            " which means to set the working directory to the directory containing the runner executable"
        ),
        widget_class=WorkingDirectoryBox,
        icon_name="insert-text-symbolic",
    ),
}


class CreateRunnerBox(VBox):
    """Box for creating a runner"""

    COL_SIDEBAR_BUTTON = 0

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        sidebar = Gtk.ListBox(visible=True)
        sidebar.connect("row-selected", self._on_sidebar_activated)

        self.stack = Gtk.Stack(visible=True)
        self.stack.set_vhomogeneous(False)
        self.stack.set_interpolate_size(True)

        toplevel_box = Gtk.HBox(visible=True)
        toplevel_box.pack_start(sidebar, False, False, 0)
        toplevel_box.add(self.stack)

        self.config_boxes: Dict[str, BaseRunnerConfigBox] = {}
        for runner_field, config_creator in RUNNER_CONFIG_SCHEMA.items():
            if not callable(config_creator.widget_class):
                continue

            stack_id = f"{runner_field}-stack"
            self.config_boxes[runner_field] = config_creator.widget_class()
            self.stack.add_named(self.config_boxes[runner_field], stack_id)
            sidebar.add(
                self._get_sidebar_button(
                    stack_id=stack_id,
                    text=_(config_creator.label),
                    tooltip=config_creator.tooltip,
                    icon_name=config_creator.icon_name,
                )
            )

        self.pack_start(toplevel_box, True, True, 0)

    def generate_widgets(self):
        return super().generate_widgets()

    def to_dict(self) -> Dict[str, Any]:
        runner_dict = {}
        for runner_field in RUNNER_CONFIG_SCHEMA.keys():
            field_value = self.config_boxes[runner_field].to_dict()
            if field_value:
                runner_dict[runner_field] = field_value

        return runner_dict

    def from_dict(self, runner_dict: Dict[str, Any]) -> bool:
        return all(
            runner_box_widgets.from_dict(runner_dict.get(runner_field))
            for runner_field, runner_box_widgets in self.config_boxes.items()
        )

    def _on_sidebar_activated(self, _sidebar, row):
        row_widgets = row.get_children()
        if not row_widgets:
            return

        sidebar_row_button_box = row_widgets[CreateRunnerBox.COL_SIDEBAR_BUTTON]
        if hasattr(sidebar_row_button_box, "stack_id"):
            stack_id = sidebar_row_button_box.stack_id
            self.stack.set_visible_child_name(stack_id)

    def _get_sidebar_button(self, stack_id, text, tooltip, icon_name):
        hbox = Gtk.HBox(visible=True)
        hbox.stack_id = stack_id
        hbox.set_margin_top(12)
        hbox.set_margin_bottom(12)
        hbox.set_tooltip_text(tooltip)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        icon.show()
        hbox.pack_start(icon, False, False, 6)

        label = Gtk.Label(text, visible=True)
        label.set_alignment(0, 0.5)
        hbox.pack_start(label, False, False, 0)
        return hbox


class RunnerConfigEditMode(Enum):
    CREATE = 0
    UPDATE = 1


class RunnerConfigFileFormats(str, Enum):
    JSON = "json"
    YAML = "yml"


class EditRunnerConfigDialog(GameDialogCommon):
    """Allow creation of a runner config JSON"""

    __gsignals__ = {"runner-saved": (GObject.SIGNAL_RUN_FIRST, None, (str,))}

    def __init__(self, parent=None, edit_mode=RunnerConfigEditMode.CREATE, runner: Optional[Runner] = None):
        super().__init__(_("Create New Runner Config"), config_level="system", parent=parent)

        label = Label(_("Runner File Prefix"))
        self._create_runner_box = CreateRunnerBox()

        self._runner_name_entry = Gtk.Entry(visible=True)
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
                self._runner_format_dropdown.set_sensitive(False)

        self.save_button.set_sensitive(bool(self._runner_name_entry.get_text()))

        name_box = Gtk.Box(visible=True, spacing=12, margin_right=12, margin_left=12)
        name_box.pack_start(label, False, False, 0)
        name_box.pack_start(self._runner_name_entry, True, True, 0)

        self.get_content_area().pack_start(name_box, False, False, 0)
        self.get_content_area().pack_start(runner_fileformat_box, False, False, 0)
        self.get_content_area().pack_start(self._create_runner_box, True, True, 0)
        self.show_all()

    def _get_runner_format_box(self):
        box = Gtk.Box(visible=True, spacing=12, margin_right=12, margin_left=12)
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

    def _inject_runner(self, runner_name, runner_config_path):
        runner_name = self._runner_name_entry.get_text()
        if not runner_name:
            return

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

        if runner_messages := ModelRunner.validate(runner_dict):
            ErrorDialog(
                error=f"Cannot save new runner '{runner_name}'\n"
                + "\n".join([f"{error.key_path}: {error.message}" for error in runner_messages.get_errors()]),
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
        if self._inject_runner(runner_name, runner_config_path):
            self.emit("runner-saved", runner_name)

        self.destroy()
