"""Widget generators and their signal handlers"""

import shlex
from copy import deepcopy
from gettext import gettext as _
from typing import Any, cast

# Third Party Libraries
from gi.repository import Gdk, Gio, Gtk

# Lutris Modules
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.config.boxes import ConfigBox, ConfigWidgetGenerator
from lutris.gui.widgets.common import Label
from lutris.util.log import logger

LAUNCH_CONFIG_KEYS = ["command", "exe", "args", "working_dir"]

LAUNCH_CONFIG_GAME_OPTIONS: list[dict[str, Any]] = [
    {
        "option": "name",
        "type": "string",
        "label": _("Name"),
        "default": _("New Launch Config"),
        "help": _("The name of the Launch Config"),
    },
    {
        "option": "command",
        "type": "command_line",
        "label": _("Command"),
        "help": _(
            "The command to run. The command is split on spaces. Double quotes can be used to prevent word splitting"
        ),
    },
    {
        "option": "exe",
        "type": "file",
        "label": _("Executable"),
        "help": _(
            "Executable file that is PASSED as the first argument to the runner executable or `command` option if set"
        ),
    },
    {
        "option": "args",
        "type": "string",
        "label": _("Arguments"),
        "help": _("The argumetns for the launch config"),
        "validator": shlex.split,
    },
    {
        "option": "working_dir",
        "type": "directory",
        "label": _("Working directory"),
        "help": _(
            "The location where the executable is run from.\nBy default, Lutris uses the directory of the executable."
        ),
    },
]


NEW_LAUNCH_CONFIG_FMT = _("New Launch Config %d")


new_config_index = 0


def generate_next_index() -> int:
    global new_config_index
    new_config_index += 1
    return new_config_index


def generate_launch_config_from_primary_config(game_config: dict[Any, Any]) -> dict[Any, Any]:
    """
    Generates a launch config using the primary game config
    The values are deep copied to the new launch config

    The keys are taking from the LAUNCH_CONFIG_KEYS set

    Return a reference to the new config
    """
    new_launch_config = {"name": NEW_LAUNCH_CONFIG_FMT % generate_next_index()}
    for option_key in LAUNCH_CONFIG_KEYS:
        if option_key in game_config:
            new_launch_config[option_key] = deepcopy(game_config[option_key])

    game_config.setdefault("launch_configs", []).append(new_launch_config)
    return new_launch_config


class GameBox(ConfigBox):
    config_section = "game"

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game, **kwargs):
        ConfigBox.__init__(
            self,
            config_level,
            lutris_config,
            game,
            widget_container=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True),
            **kwargs,
        )
        # Store off a separate widget generator for launch configs
        self._launch_config_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=False)
        self._launch_config_widget_generator: ConfigWidgetGenerator | None = None

        self.runner = game.runner
        if not self.runner:
            logger.warning("No runner in game supplied to GameBox")
            return

        self.options = self.runner.game_options

        self._launch_config_dropdown_index = 0
        self._launch_config_box: Gtk.Box = self._get_launch_config_box()

        action_id = "remove"
        remove_action = Gio.SimpleAction.new(name=action_id)
        remove_action.connect("activate", self._on_delete_action)
        option_action_group = Gio.SimpleActionGroup()
        option_action_group.insert(remove_action)
        self.insert_action_group("option", option_action_group)

        menu = Gio.Menu()
        menu.append(_("Remove Launch Config"), f"option.{action_id}")
        self._popup_menu = Gtk.Popover.new_from_model(relative_to=self._launch_config_box, model=menu)

        self.pack_start(self._launch_config_box, False, True, 0)
        self.pack_start(self._launch_config_container, True, True, 0)

    @property
    def launch_config_dropdown_index(self) -> int:
        return self._launch_config_dropdown_index

    @launch_config_dropdown_index.setter
    def launch_config_dropdown_index(self, value: int) -> None:
        self._launch_config_dropdown_index = value
        # Enable/disable the delete options based on the selected index
        self._delete_button.set_visible(self._launch_config_dropdown_index != 0)

    # "launch_config" methods
    def _get_launch_config_box(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin_start=18, spacing=12, margin_bottom=6, margin=18)
        label = Label(_("LaunchConfig"))

        self._add_button = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        self._add_button.set_tooltip_text(_("Add new launch config"))
        self._add_button.set_visible(True)
        self._add_button.connect("clicked", self._on_add)

        self._delete_button = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
        self._delete_button.set_tooltip_text(_("Remove selected launch config"))
        # Only visible when the launch config is Not set to the primary value
        self._delete_button.set_visible(False)
        self._delete_button.set_no_show_all(True)
        self._delete_button.connect("clicked", self._on_delete_button)

        config_liststore = self._get_launch_config_liststore()
        self._launch_config_dropdown: Gtk.ComboBox = Gtk.ComboBox.new_with_model(config_liststore)
        self._launch_config_dropdown.set_tooltip_text(
            _("Set the name of the launch config.\n%s launch config name cannot be changed")
            % Game.PRIMARY_LAUNCH_CONFIG_NAME
        )
        self._launch_config_dropdown.set_id_column(0)
        self._launch_config_dropdown.set_active_id(Game.PRIMARY_LAUNCH_CONFIG_NAME)
        self._launch_config_dropdown_index = self._launch_config_dropdown.get_active()
        self._launch_config_dropdown.connect("changed", self._on_launch_config_combo_changed)
        cell_renderer = Gtk.CellRendererText()
        self._launch_config_dropdown.pack_start(cell_renderer, True)
        self._launch_config_dropdown.add_attribute(cell_renderer, "text", 0)
        config_liststore.connect("row_changed", self._launch_config_liststore_changed)

        event_box = Gtk.EventBox(visible=True)
        event_box.connect("button-press-event", self._launch_config_dropdown_popup_menu)
        event_box.add(self._launch_config_dropdown)

        box.pack_start(label, False, False, 0)
        box.pack_start(event_box, True, True, 0)
        box.pack_start(self._add_button, False, False, 0)
        box.pack_start(self._delete_button, False, False, 0)

        return box

    def _on_launch_config_combo_changed(self, widget: Gtk.ComboBox) -> None:
        """Action called when either the active dropdown selection is changed
        or the text entry is modified."""

        active_entry_changed = self._update_active_launch_config()
        if active_entry_changed:
            # Update the widget values with the launch config if the dropdown selection changes
            self.update_launch_config_widget_values()
        self.update_widgets()

    def _get_launch_config_liststore(self) -> Gtk.ListStore:
        """Populated with the default game config"""
        config_liststore = Gtk.ListStore(str)
        config_liststore.append((str(Game.PRIMARY_LAUNCH_CONFIG_NAME),))

        if self.lutris_config.raw_game_config:
            game_config = self.lutris_config.raw_game_config
            launch_configs = game_config.get("launch_configs", [])
            for launch_config in launch_configs:
                config_name = launch_config.get("name")
                if not config_name:
                    config_name = NEW_LAUNCH_CONFIG_FMT % generate_next_index()
                config_liststore.append((config_name,))
        return config_liststore

    def _add_launch_config(self) -> None:
        """Adds a new text entry for the launch config name"""
        config_liststore = cast(Gtk.ListStore, self._launch_config_dropdown.get_model())

        if self.lutris_config:
            # Populate the launch config with the values from the primary config
            launch_config = generate_launch_config_from_primary_config(self.lutris_config.raw_game_config)
            config_iter = config_liststore.append((launch_config["name"],))
        else:
            config_iter = config_liststore.append((NEW_LAUNCH_CONFIG_FMT % generate_next_index(),))

        # Change the dropdown to show the newly added launch config
        self._launch_config_dropdown.set_active_iter(config_iter)

    def _on_add(self, _widget) -> None:
        self._add_launch_config()

    def _on_delete(self, _widget, launch_config_iter: Gtk.TreeIter) -> None:
        config_model = cast(Gtk.ListStore, self._launch_config_dropdown.get_model())
        config_liststore: Gtk.ListStore = config_model

        old_dropdown_index = self.launch_config_dropdown_index

        # Delete the launch config from the game config object
        if old_dropdown_index > 0:  # Index 0 refers to the primary config
            launch_config_index = old_dropdown_index - 1
            if self.lutris_config:
                raw_game_config = self.lutris_config.raw_game_config
                raw_launch_configs = raw_game_config.get("launch_configs", [])
                if launch_config_index < len(raw_launch_configs):
                    del raw_launch_configs[launch_config_index]

        iter_valid = config_liststore.remove(launch_config_iter)
        # The remove method updates the passed in iterator in place
        if iter_valid:
            self._launch_config_dropdown.set_active_iter(launch_config_iter)
        else:
            self._launch_config_dropdown.set_active_id(Game.PRIMARY_LAUNCH_CONFIG_NAME)

    def _launch_config_dropdown_popup_menu(self, widget, event: Gdk.EventButton) -> None:
        """Create popup menu that can be remove the launch config"""
        if event.button != Gdk.BUTTON_SECONDARY:
            return

        # The primary entry isn't a launch config so it cannot be deleted
        if self.launch_config_dropdown_index == 0:
            return

        click_rect = Gdk.Rectangle()
        click_rect.x = int(event.x)
        click_rect.y = int(event.y)
        self._popup_menu.set_relative_to(widget)
        self._popup_menu.set_pointing_to(click_rect)
        self._popup_menu.popup()

    def _on_delete_button(self, _widget) -> None:
        if config_tree_iter := self._launch_config_dropdown.get_active_iter():
            self._on_delete(self._launch_config_dropdown, config_tree_iter)

    def _on_delete_action(self, action, parameter) -> None:
        self._on_delete_button(self._launch_config_dropdown)

    def _update_active_launch_config(self) -> bool:
        """Update the launch config entries being shown in the Config Generator
        Returns true when the selected item changes
        """
        # Update the launch config index member
        if self._launch_config_dropdown.get_active() == -1:
            return False

        self.launch_config_dropdown_index = self._launch_config_dropdown.get_active()
        if self.launch_config_dropdown_index == 0:
            self.set_primary_config_container_visibility(True)
            self.set_launch_config_container_visibility(False)
        else:
            self.set_primary_config_container_visibility(False)
            self.set_launch_config_container_visibility(True)
            self.set_active_launch_config(self._launch_config_dropdown_index - 1)

        return True

    @property
    def advanced_visibility(self):
        return self._advanced_visibility

    @advanced_visibility.setter
    def advanced_visibility(self, value):
        """When the advanced setting is turned off, set the box that contains
        the Launch Config drop down widgets to hidden.
        Afterwards alway show the primary launch config

        When the setting is turned back on, the containing box visibality
        will be reset to true
        """

        if value:
            self._launch_config_box.set_visible(True)
        else:
            # Set the combobox active ID to the Primary Launch Config name
            # to trigger the event to show the primary launch config again
            # Aftewards hiden the launch config dropdown
            self._launch_config_dropdown.set_active_id(Game.PRIMARY_LAUNCH_CONFIG_NAME)
            self._launch_config_box.set_visible(False)

        # Call the normal base class advanced functionality
        self._advanced_visibility = value
        self.update_widgets()

    def generate_widgets(self) -> None:
        """Generate the Launch Config widgets, with the normal widgets"""
        super().generate_widgets()
        self.generate_launch_config_widgets()

    def generate_launch_config_widgets(self) -> None:
        """Adds widgets for the launch config."""

        launch_config_gen = self.get_launch_config_widget_generator()
        for option in LAUNCH_CONFIG_GAME_OPTIONS:
            try:
                launch_config_gen.add_container(option)
            except Exception as ex:
                logger.exception("Failed to generate option widget for '%s': %s", option.get("option"), ex)

        self.update_widgets()

    def get_launch_config_widget_generator(self) -> ConfigWidgetGenerator:
        """Returns a generator for creating widgets for the launch config"""
        if self._launch_config_widget_generator:
            return self._launch_config_widget_generator

        self._launch_config_widget_generator = ConfigWidgetGenerator(self, self._launch_config_container)
        self._launch_config_widget_generator.changed.register(self._on_launch_config_option_changed)
        # Initially the primary config widgets are showing, so hide the launch config widget container
        # But make sure the children are visible by calling show_all() first
        if self._launch_config_container:
            self._launch_config_container.show_all()
        self.set_launch_config_container_visibility(False)

        return self._launch_config_widget_generator

    def update_widgets(self):
        """Update both the primary game config and launch config widgets"""
        super().update_widgets()
        if self._launch_config_widget_generator:
            self._launch_config_widget_generator.update_widgets()

    def update_launch_config_widget_values(self) -> None:
        if self._launch_config_widget_generator:
            self._launch_config_widget_generator.update_widget_values()

    def set_primary_config_container_visibility(self, visible: bool) -> None:
        if self._widget_container:
            self._widget_container.set_visible(visible)

    def set_launch_config_container_visibility(self, visible: bool) -> None:
        if self._launch_config_container:
            self._launch_config_container.set_visible(visible)

    def set_active_launch_config(self, index: int) -> None:
        """Update the launch config widget generator to show the launch config values
        at the specified index in the "launch_configs" array
        """
        if self._launch_config_widget_generator:
            raw_launch_configs = self._launch_config_widget_generator.raw_config.get("launch_configs", [])
            if index < len(raw_launch_configs):
                self._launch_config_widget_generator.raw_config_view = raw_launch_configs[index]

    def _on_launch_config_option_changed(self, option_key, new_value) -> None:
        """Updates the launch config list with the name"""
        if option_key != "name":
            return

        if self._launch_config_dropdown_index > 0:
            config_liststore = cast(Gtk.ListStore, self._launch_config_dropdown.get_model())
            config_iter = config_liststore.iter_nth_child(None, self.launch_config_dropdown_index)
            if config_iter:
                config_liststore.set(config_iter, 0, new_value)

    def _launch_config_liststore_changed(self, _tree_model, _path, iter):
        self._launch_config_dropdown.set_active_iter(iter)
