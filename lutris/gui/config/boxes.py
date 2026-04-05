"""Widget generators and their signal handlers"""

import os
from abc import abstractmethod

# Standard Library
# pylint: disable=no-member,too-many-public-methods
from gettext import gettext as _
from typing import Any

# Third Party Libraries
from gi.repository import Gtk, Pango

# Lutris Modules
from lutris import settings, sysoptions
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.config.widget_generator import WidgetGenerator
from lutris.gui.widgets.common import VBox
from lutris.runners import InvalidRunnerError, import_runner
from lutris.util.log import logger
from lutris.util.wine.wine import clear_wine_version_cache


def set_option_wrapper_style_class(wrapper: Gtk.Widget, class_name: str | None):
    """Sets a particular CSS class on a wrapper, and removes any other classes that start
    with 'option-wrapper-' so there's only one o these classes."""
    for cls in wrapper.get_css_classes():
        if cls.startswith("option-wrapper-") and cls != class_name:
            wrapper.remove_css_class(cls)

    if class_name:
        wrapper.add_css_class(class_name)


class AdvancedSettingsBox(VBox):
    """Intermediate vbox class for expsoing the Advanced Visibility options"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._advanced_visibility = False

    @property
    def advanced_visibility(self):
        return self._advanced_visibility

    @advanced_visibility.setter
    def advanced_visibility(self, value):
        """Sets the visibility of every 'advanced' option and every section that
        contains only 'advanced' options."""
        self._advanced_visibility = value
        self.update_widgets()

    @abstractmethod
    def update_widgets(self):
        """Updates widgets on visibility change; this method must be
        implemented by a subclass."""
        raise NotImplementedError()


class ConfigBox(AdvancedSettingsBox):
    """Dynamically generate a vbox built upon on a python dict."""

    config_section = NotImplemented

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.options = []
        self.config_level = config_level
        self.lutris_config = lutris_config
        self.game = game
        self.config = None
        self.raw_config = None
        self.files = []
        self.files_list_store = None
        self._widget_generator = None
        self._filter = ""
        self._filter_text = ""

        self.no_options_label = Gtk.Label(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.no_options_label.set_wrap(True)
        self.no_options_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.no_options_label.set_hexpand(True)
        self.no_options_label.set_vexpand(True)
        self.append(self.no_options_label)

    @property
    def filter(self) -> str:
        return self._filter

    @filter.setter
    def filter(self, value: str) -> None:
        """Sets the visibility of the options that have some text in the label or
        help-text."""
        self._filter = value
        self._filter_text = value.casefold()
        self.update_widgets()

    def generate_top_info_box(self, text):
        """Add a top section with general help text for the current tab"""
        help_box = Gtk.Box()
        help_box.set_margin_start(15)
        help_box.set_margin_end(15)
        help_box.set_margin_bottom(12)

        icon = Gtk.Image.new_from_icon_name("dialog-information")
        icon.set_margin_start(5)
        icon.set_margin_end(5)
        help_box.append(icon)

        title_label = Gtk.Label(label="<i>%s</i>" % text)
        title_label.set_wrap(True)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_use_markup(True)
        title_label.set_margin_start(5)
        title_label.set_margin_end(5)
        help_box.append(title_label)

        self.append(help_box)
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_bottom(6)
        self.append(separator)

    def get_widget_generator(self) -> "ConfigWidgetGenerator":
        """Returns an object that creates option widgets and tracks them; this is
        lazy-initialized, but repeated calls return the same generator."""
        if self._widget_generator:
            return self._widget_generator

        gen = ConfigWidgetGenerator(self)

        if self.game and self.game.directory:
            gen.default_directory = self.game.directory
        elif self.game and self.game.has_runner and self.game.runner.has_working_dir:
            gen.default_directory = self.game.runner.working_dir
        elif self.lutris_config:
            gen.default_directory = self.lutris_config.system_config.get("game_path") or os.path.expanduser("~")
        else:
            gen.default_directory = os.path.expanduser("~")

        self._widget_generator = gen
        return gen

    def filter_widget(self, option_container: Gtk.Widget) -> bool:
        """Called by the widget generate to filter option containers; return true for
        those that should be visible."""
        if not self.advanced_visibility:
            is_advanced = hasattr(option_container, "lutris_advanced") and option_container.lutris_advanced
            if is_advanced:
                # Record that we hid this because it was advanced, not because of ordinary
                # visibility
                option_container.lutris_advanced_hidden = True  # type:ignore[attr-defined]
                return False

        filter_text = self._filter_text
        if filter_text and hasattr(option_container, "lutris_option_label"):
            label = option_container.lutris_option_label.casefold()
            helptext = option_container.lutris_option_helptext.casefold()  # type:ignore[attr-defined]
            if filter_text not in label and filter_text not in helptext:
                return False

        return True

    def generate_widgets(self):
        """Parse the config dict and generates widget accordingly."""
        # Select config section.
        if self.config_section == "game":
            self.config = self.lutris_config.game_config
            self.raw_config = self.lutris_config.raw_game_config
        elif self.config_section == "runner":
            self.config = self.lutris_config.runner_config
            self.raw_config = self.lutris_config.raw_runner_config
        elif self.config_section == "system":
            self.config = self.lutris_config.system_config
            self.raw_config = self.lutris_config.raw_system_config

        gen = self.get_widget_generator()

        # Go thru all options.
        for option in self.options:
            try:
                if "scope" in option:
                    if self.config_level not in option["scope"]:
                        continue

                # Generate option widget
                gen.add_container(option)
            except Exception as ex:
                logger.exception("Failed to generate option widget for '%s': %s", option.get("option"), ex)

        show_advanced = settings.read_setting("show_advanced_options") == "True"
        self._advanced_visibility = show_advanced
        gen.update_widgets()

    def update_widgets(self):
        if self._widget_generator:
            self._widget_generator.update_widgets()


class GameBox(ConfigBox):
    config_section = "game"

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game, **kwargs):
        ConfigBox.__init__(self, config_level, lutris_config, game, **kwargs)
        self.runner = game.runner
        if self.runner:
            self.options = self.runner.game_options
        else:
            logger.warning("No runner in game supplied to GameBox")


class RunnerBox(ConfigBox):
    """Configuration box for runner specific options"""

    config_section = "runner"

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game | None = None, **kwargs):
        ConfigBox.__init__(self, config_level, lutris_config, game, **kwargs)

        try:
            self.runner = import_runner(self.lutris_config.runner_slug)() if self.lutris_config.runner_slug else None
        except InvalidRunnerError:
            self.runner = None
        if self.runner:
            self.options = self.runner.get_runner_options()

        if lutris_config.level == "game":
            self.generate_top_info_box(
                _("If modified, these options supersede the same options from the base runner configuration.")
            )

    def generate_widgets(self):
        # Better safe than sorry - we search of Wine versions in directories
        # we do not control, so let's keep up to date more aggresively.
        clear_wine_version_cache()
        return super().generate_widgets()


class SystemConfigBox(ConfigBox):
    config_section = "system"

    def __init__(self, config_level: str, lutris_config: LutrisConfig, **kwargs) -> None:
        ConfigBox.__init__(self, config_level, lutris_config, **kwargs)
        self.runner = None
        runner_slug = self.lutris_config.runner_slug

        if runner_slug:
            self.options = sysoptions.with_runner_overrides(runner_slug)
        else:
            self.options = sysoptions.system_options

        if lutris_config.game_config_id and runner_slug:
            self.generate_top_info_box(
                _(
                    "If modified, these options supersede the same options from "
                    "the base runner configuration, which themselves supersede "
                    "the global preferences."
                )
            )
        elif runner_slug:
            self.generate_top_info_box(
                _("If modified, these options supersede the same options from the global preferences.")
            )


class ConfigWidgetGenerator(WidgetGenerator):
    def __init__(self, parent: ConfigBox) -> None:
        super().__init__(parent, parent.lutris_config)

        if parent.config is None or parent.raw_config is None:
            raise RuntimeError("Widgets can't be generated before the config is initialized.")

        self.config = parent.config
        self.raw_config = parent.raw_config
        self.lutris_config = parent.lutris_config
        self.reset_buttons: dict[str, Gtk.Button] = {}

    def get_setting(self, option_key: str, default: Any) -> Any:
        if option_key in self.config:
            return self.config.get(option_key)
        else:
            return default

    def update_option_container(self, option, container: Gtk.Widget, wrapper: Gtk.Widget) -> None:
        super().update_option_container(option, container, wrapper)
        option_key = option["option"]

        if option_key in self.raw_config:
            set_option_wrapper_style_class(wrapper, "option-wrapper-assigned-here")
        else:
            default = self.get_default(option)
            value = self.get_setting(option_key, default)

            if value != default:
                set_option_wrapper_style_class(wrapper, "option-wrapper-non-default")
            else:
                set_option_wrapper_style_class(wrapper, None)

    def create_option_container(self, option: dict[str, Any], wrapper: Gtk.Widget) -> Gtk.Widget:
        option_key = option["option"]
        reset_container = Gtk.Box(visible=True)
        reset_container.set_margin_start(18)
        wrapper.set_hexpand(True)
        reset_container.append(wrapper)

        reset_button = Gtk.Button.new_from_icon_name("edit-undo-symbolic")
        reset_button.add_css_class("reset-button")
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button.set_halign(Gtk.Align.CENTER)
        reset_button.set_margin_bottom(6)
        reset_button.set_has_frame(False)
        reset_button.set_tooltip_text(_("Reset option to global or default config"))
        reset_button.connect("clicked", self.on_reset_button_clicked, option)
        self.reset_buttons[option_key] = reset_button

        if option_key not in self.raw_config:
            reset_button.set_visible(False)

        placeholder = Gtk.Box()
        placeholder.set_size_request(28, -1)

        placeholder.append(reset_button)
        placeholder.set_margin_start(5)
        placeholder.set_margin_end(5)
        reset_container.append(placeholder)
        return super().create_option_container(option, reset_container)

    def get_visibility(self, option: dict[str, Any]) -> bool:
        option_container = self.option_containers[option["option"]]
        option_container.lutris_advanced_hidden = False  # type:ignore[attr-defined]
        option_visibility = super().get_visibility(option)

        if not option_visibility:
            return False

        return self.parent.filter_widget(option_container)

    def get_tooltip(self, option: dict[str, Any], value: Any, default: Any):
        tooltip = super().get_tooltip(option, value, default)
        option_key = option["option"]
        if value != default and option_key not in self.raw_config:
            tooltip = tooltip + "\n\n" if tooltip else ""
            tooltip += _("<i>(Italic indicates that this option is modified in a lower configuration level.)</i>")
        return tooltip

    def update_widgets(self):
        super().update_widgets()

        def get_no_options_message() -> str | None:
            if self.option_containers:
                for container in self.option_containers.values():
                    if container.get_visible():
                        return None

                if self.parent.filter:
                    return _("No options match '%s'") % self.parent.filter
                elif any(c.lutris_advanced_hidden for c in self.option_containers.values()):  # type:ignore[attr-defined]
                    return _("Only advanced options available")

            return _("No options available")

        message = get_no_options_message()
        if message:
            self.parent.no_options_label.set_text(message)
            self.parent.no_options_label.set_visible(True)
        else:
            self.parent.no_options_label.set_visible(False)

    def on_reset_button_clicked(self, btn, option):
        """Clear option (remove from config, reset option widget)."""
        option_key = option["option"]
        wrapper = self.wrappers[option_key]

        btn.set_visible(False)

        self.raw_config.pop(option_key, None)
        self.lutris_config.update_cascaded_config()

        self.generate_widget(option, wrapper=wrapper)
        self.update_widgets()

    def on_changed(self, option_key, new_value):
        """Common actions when value changed on a widget"""
        self.raw_config[option_key] = new_value
        self.config[option_key] = new_value
        reset_btn = self.reset_buttons.get(option_key)

        if reset_btn:
            reset_btn.set_visible(True)

        super().on_changed(option_key, new_value)
