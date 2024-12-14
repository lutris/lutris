"""Widget generators and their signal handlers"""

import os

# Standard Library
# pylint: disable=no-member,too-many-public-methods
from gettext import gettext as _
from typing import Any, Dict, Optional

# Third Party Libraries
from gi.repository import Gtk

# Lutris Modules
from lutris import settings, sysoptions
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.config.widget_generator import SectionFrame, WidgetGenerator
from lutris.gui.widgets.common import Label, VBox
from lutris.runners import InvalidRunnerError, import_runner
from lutris.util.log import logger
from lutris.util.wine.wine import clear_wine_version_cache


class ConfigBox(VBox):
    """Dynamically generate a vbox built upon on a python dict."""

    config_section = NotImplemented

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game = None) -> None:
        super().__init__()
        self.options = []
        self.config_level = config_level
        self.lutris_config = lutris_config
        self.game = game
        self.config = None
        self.raw_config = None
        self.files = []
        self.files_list_store = None
        self.reset_buttons = {}
        self.wrappers = {}
        self.message_updaters = []
        self._advanced_visibility = False
        self._filter = ""

    @property
    def advanced_visibility(self):
        return self._advanced_visibility

    @advanced_visibility.setter
    def advanced_visibility(self, value):
        """Sets the visibility of every 'advanced' option and every section that
        contains only 'advanced' options."""
        self._advanced_visibility = value
        self.update_option_visibility()

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, value):
        """Sets the visibility of the options that have some text in the label or
        help-text."""
        self._filter = value
        self.update_option_visibility()

    def update_option_visibility(self):
        """Recursively searches out all the options and shows or hides them according to
        the filter and advanced-visibility settings."""

        def update_widgets(widgets):
            filter_text = self.filter.lower()

            visible_count = 0
            for widget in widgets:
                if isinstance(widget, SectionFrame):
                    frame_visible_count = update_widgets(widget.vbox.get_children())
                    visible_count += frame_visible_count
                    widget.set_visible(frame_visible_count > 0)
                else:
                    widget_visible = not hasattr(widget, "lutris_visible") or widget.lutris_visible
                    widget_visible = widget_visible and (
                        self.advanced_visibility or not hasattr(widget, "lutris_advanced") or not widget.lutris_advanced
                    )
                    if widget_visible and filter_text and hasattr(widget, "lutris_option_label"):
                        label = widget.lutris_option_label.lower()
                        helptext = widget.lutris_option_helptext.lower()
                        if filter_text not in label and filter_text not in helptext:
                            widget_visible = False
                    widget.set_visible(widget_visible)
                    widget.set_no_show_all(not widget_visible)
                    if widget_visible:
                        visible_count += 1
                        widget.show_all()

            return visible_count

        update_widgets(self.get_children())

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
        if self.config is None or self.raw_config is None:
            raise RuntimeError("Widgets can't be generated before the config is initialized.")

        gen = ConfigWidgetGenerator(self, self.config, self.raw_config)
        gen.changed.register(self.on_option_changed)

        if self.game and self.game.directory:
            gen.default_directory = self.game.directory
        elif self.game and self.game.has_runner:
            gen.default_directory = self.game.runner.working_dir
        elif self.lutris_config:
            gen.default_directory = self.lutris_config.system_config.get("game_path") or os.path.expanduser("~")
        else:
            gen.default_directory = os.path.expanduser("~")

        return gen

    def generate_widgets(self):  # noqa: C901 # pylint: disable=too-many-branches,too-many-statements
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
            option = option.copy()  # we will mutate this, so let's not alter the original

            try:
                if "scope" in option:
                    if self.config_level not in option["scope"]:
                        continue
                option_key = option["option"]
                value = self.config.get(option_key)

                # Generate option widget
                option_container = gen.add_container(option, value)
                if option_container:
                    self.wrappers[option_key] = gen.wrapper
                    self.reset_buttons[option_key] = gen.reset_btn
                    self.message_updaters += gen.message_updaters
                    gen.reset_btn.connect("clicked", self.on_reset_button_clicked, option, gen.wrapper)
            except Exception as ex:
                logger.exception("Failed to generate option widget for '%s': %s", option.get("option"), ex)

        self.update_warnings()
        self.show_all()

        show_advanced = settings.read_setting("show_advanced_options") == "True"
        self.advanced_visibility = show_advanced

    def update_warnings(self) -> None:
        for updater in self.message_updaters:
            updater(self.lutris_config)
        self.update_option_visibility()

    def on_option_changed(self, option_name, value):
        """Common actions when value changed on a widget"""
        self.raw_config[option_name] = value
        self.config[option_name] = value
        reset_btn = self.reset_buttons.get(option_name)
        wrapper = self.wrappers.get(option_name)

        if reset_btn:
            reset_btn.set_visible(True)

        if wrapper:
            self.set_style_property("font-weight", "bold", wrapper)

        self.update_warnings()

    def on_reset_button_clicked(self, btn, option, wrapper):
        """Clear option (remove from config, reset option widget)."""
        option_key = option["option"]
        current_value = self.config[option_key]

        btn.set_visible(False)
        self.set_style_property("font-weight", "normal", wrapper)
        self.raw_config.pop(option_key, None)
        self.lutris_config.update_cascaded_config()

        reset_value = self.config.get(option_key)
        if current_value == reset_value:
            return

        gen = self.get_widget_generator()
        gen.generate_widget(option, reset_value, wrapper=wrapper)
        self.update_warnings()


class GameBox(ConfigBox):
    config_section = "game"

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game):
        ConfigBox.__init__(self, config_level, lutris_config, game)
        self.runner = game.runner
        if self.runner:
            self.options = self.runner.game_options
        else:
            logger.warning("No runner in game supplied to GameBox")


class RunnerBox(ConfigBox):
    """Configuration box for runner specific options"""

    config_section = "runner"

    def __init__(self, config_level: str, lutris_config: LutrisConfig, game: Game = None):
        ConfigBox.__init__(self, config_level, lutris_config, game)

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

    def __init__(self, config_level: str, lutris_config: LutrisConfig) -> None:
        ConfigBox.__init__(self, config_level, lutris_config)
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
    def __init__(self, parent, config, raw_config) -> None:
        super().__init__(parent)
        self.config = config
        self.raw_config = raw_config
        self.reset_btn: Optional[Gtk.Button] = None

    def get_setting(self, option_key: str) -> Any:
        return self.config.get(option_key)

    def create_wrapper_box(self, option: Dict[str, Any], value: Any, default: Any) -> Optional[Gtk.Box]:
        option_key = option["option"]
        wrapper = super().create_wrapper_box(option, value, default)

        if wrapper:
            if option_key in self.raw_config:
                self.set_style_property("font-weight", "bold", wrapper)
            elif value != default:
                self.set_style_property("font-style", "italic", wrapper)

        return wrapper

    @staticmethod
    def set_style_property(property_, value, wrapper):
        """Add custom style."""
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data("GtkHBox {{{}: {};}}".format(property_, value).encode())
        style_context = wrapper.get_style_context()
        style_context.add_provider(style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def create_option_container(self, option: Dict[str, Any], wrapper: Gtk.Widget) -> Gtk.Widget:
        option_key = option["option"]
        reset_container = Gtk.Box(visible=True)
        reset_container.set_margin_left(18)
        reset_container.pack_start(wrapper, True, True, 0)

        self.reset_btn = Gtk.Button.new_from_icon_name("edit-undo-symbolic", Gtk.IconSize.MENU)
        self.reset_btn.set_valign(Gtk.Align.CENTER)
        self.reset_btn.set_margin_bottom(6)
        self.reset_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.reset_btn.set_tooltip_text(_("Reset option to global or default config"))

        if option_key not in self.raw_config:
            self.reset_btn.set_visible(False)
            self.reset_btn.set_no_show_all(True)

        placeholder = Gtk.Box()
        placeholder.set_size_request(32, 32)

        placeholder.pack_start(self.reset_btn, False, False, 0)
        reset_container.pack_end(placeholder, False, False, 5)
        return super().create_option_container(option, reset_container)

    def get_tooltip(self, option: Dict[str, Any], value: Any, default: Any):
        tooltip = super().get_tooltip(option, value, default)
        option_key = option["option"]
        if value != default and option_key not in self.raw_config:
            tooltip = tooltip + "\n\n" if tooltip else ""
            tooltip += _("<i>(Italic indicates that this option is modified in a lower configuration level.)</i>")
        return tooltip
