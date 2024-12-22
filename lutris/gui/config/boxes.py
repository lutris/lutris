"""Widget generators and their signal handlers"""

import os

# Standard Library
# pylint: disable=no-member,too-many-public-methods
from gettext import gettext as _
from typing import Any, Callable, Dict, Optional, Union

# Third Party Libraries
from gi.repository import Gtk

# Lutris Modules
from lutris import settings, sysoptions
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.config.widget_generator import WidgetGenerator, merge_flag_callables, set_style_property
from lutris.gui.widgets.common import Label, VBox
from lutris.runners import InvalidRunnerError, import_runner
from lutris.util.log import logger
from lutris.util.wine.wine import clear_wine_version_cache


class ConfigBox(VBox):
    """Dynamically generate a vbox built upon on a python dict."""

    config_section = NotImplemented

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game = None, **kwargs) -> None:
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
        self._advanced_visibility = False
        self._filter = ""
        self._filter_text = ""

    @property
    def advanced_visibility(self):
        return self._advanced_visibility

    @advanced_visibility.setter
    def advanced_visibility(self, value):
        """Sets the visibility of every 'advanced' option and every section that
        contains only 'advanced' options."""
        self._advanced_visibility = value
        self.update_widgets()

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, value):
        """Sets the visibility of the options that have some text in the label or
        help-text."""
        self._filter = value
        self._filter_text = value.casefold()
        self.update_widgets()

    def generate_top_info_box(self, text):
        """Add a top section with general help text for the current tab"""
        help_box = Gtk.Box()
        help_box.set_margin_left(15)
        help_box.set_margin_right(15)
        help_box.set_margin_bottom(5)

        icon = Gtk.Image.new_from_icon_name("dialog-information", Gtk.IconSize.MENU)
        help_box.pack_start(icon, False, False, 5)

        title_label = Gtk.Label("<i>%s</i>" % text)
        title_label.set_line_wrap(True)
        title_label.set_alignment(0, 0.5)
        title_label.set_use_markup(True)
        help_box.pack_start(title_label, False, False, 5)

        self.pack_start(help_box, False, False, 0)
        self.pack_start(Gtk.HSeparator(), False, False, 12)

        help_box.show_all()

    def get_widget_generator(self) -> "ConfigWidgetGenerator":
        """Returns an object that creates option widgets and tracks them; this is
        lazy-initialized, but repeated calls return the same generator."""
        if self._widget_generator:
            return self._widget_generator

        gen = ConfigWidgetGenerator(self)

        if self.game and self.game.directory:
            gen.default_directory = self.game.directory
        elif self.game and self.game.has_runner:
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
                return False

        filter_text = self._filter_text
        if filter_text and hasattr(option_container, "lutris_option_label"):
            label = option_container.lutris_option_label.casefold()
            helptext = option_container.lutris_option_helptext.casefold()
            if filter_text not in label and filter_text not in helptext:
                return False

        return True

    def generate_widgets(self):
        """Parse the config dict and generates widget accordingly."""
        if not self.options:
            no_options_label = Label(_("No options available"), width_request=-1)
            no_options_label.set_halign(Gtk.Align.CENTER)
            no_options_label.set_valign(Gtk.Align.CENTER)
            self.pack_start(no_options_label, True, True, 0)
            self.show_all()
            return

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

        gen.update_widgets()

        show_advanced = settings.read_setting("show_advanced_options") == "True"
        self.advanced_visibility = show_advanced

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

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game = None, **kwargs):
        ConfigBox.__init__(self, config_level, lutris_config, game, **kwargs)

        try:
            self.runner = import_runner(self.lutris_config.runner_slug)()
        except InvalidRunnerError:
            self.runner = None
        if self.runner:
            self.options = self.runner.get_runner_options()

        if lutris_config.level == "game":
            self.generate_top_info_box(
                _("If modified, these options supersede the same options from " "the base runner configuration.")
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
                _("If modified, these options supersede the same options from " "the global preferences.")
            )


class ConfigWidgetGenerator(WidgetGenerator):
    def __init__(self, parent: ConfigBox) -> None:
        super().__init__(parent, parent.lutris_config)

        if parent.config is None or parent.raw_config is None:
            raise RuntimeError("Widgets can't be generated before the config is initialized.")

        self.config = parent.config
        self.raw_config = parent.raw_config
        self.lutris_config = parent.lutris_config
        self.reset_buttons: Dict[str, Gtk.Button] = {}

    def get_setting(self, option_key: str) -> Any:
        return self.config.get(option_key)

    def configure_wrapper_box(self, wrapper: Gtk.Widget, option: Dict[str, Any], value: Any, default: Any) -> None:
        super().configure_wrapper_box(wrapper, option, value, default)
        option_key = option["option"]

        if option_key in self.raw_config:
            set_style_property("font-weight", "bold", wrapper)
        elif value != default:
            set_style_property("font-style", "italic", wrapper)

    def create_option_container(self, option: Dict[str, Any], wrapper: Gtk.Widget) -> Gtk.Widget:
        option_key = option["option"]
        reset_container = Gtk.Box(visible=True)
        reset_container.set_margin_left(18)
        reset_container.pack_start(wrapper, True, True, 0)

        reset_button = Gtk.Button.new_from_icon_name("edit-undo-symbolic", Gtk.IconSize.MENU)
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button.set_margin_bottom(6)
        reset_button.set_relief(Gtk.ReliefStyle.NONE)
        reset_button.set_tooltip_text(_("Reset option to global or default config"))
        reset_button.connect("clicked", self.on_reset_button_clicked, option)
        self.reset_buttons[option_key] = reset_button

        if option_key not in self.raw_config:
            reset_button.set_visible(False)
            reset_button.set_no_show_all(True)

        placeholder = Gtk.Box()
        placeholder.set_size_request(32, 32)

        placeholder.pack_start(reset_button, False, False, 0)
        reset_container.pack_end(placeholder, False, False, 5)
        return super().create_option_container(option, reset_container)

    def get_visibility(self, option: Dict[str, Any]) -> Union[None, bool, Optional[Callable]]:
        option_visibility = super().get_visibility(option)

        def check_visibility(option_key, *args, **kwargs):
            option_container = self.option_containers[option_key]
            return self.parent.filter_widget(option_container)

        return merge_flag_callables([option_visibility, check_visibility])

    def get_tooltip(self, option: Dict[str, Any], value: Any, default: Any):
        tooltip = super().get_tooltip(option, value, default)
        option_key = option["option"]
        if value != default and option_key not in self.raw_config:
            tooltip = tooltip + "\n\n" if tooltip else ""
            tooltip += _("<i>(Italic indicates that this option is modified in a lower configuration level.)</i>")
        return tooltip

    def on_reset_button_clicked(self, btn, option):
        """Clear option (remove from config, reset option widget)."""
        option_key = option["option"]
        wrapper = self.wrappers[option_key]

        btn.set_visible(False)
        set_style_property("font-weight", "normal", wrapper)

        self.raw_config.pop(option_key, None)
        self.lutris_config.update_cascaded_config()

        self.generate_widget(option, wrapper=wrapper)
        self.update_widgets()

    def on_changed(self, option_key, new_value):
        """Common actions when value changed on a widget"""
        self.raw_config[option_key] = new_value
        self.config[option_key] = new_value
        reset_btn = self.reset_buttons.get(option_key)
        wrapper = self.wrappers.get(option_key)

        if reset_btn:
            reset_btn.set_visible(True)

        if wrapper:
            set_style_property("font-weight", "bold", wrapper)

        super().on_changed(option_key, new_value)
