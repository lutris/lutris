from gettext import gettext as _
from typing import Any

from gi.repository import Gio, Gtk  # type: ignore

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.widget_generator import WidgetGenerator
from lutris.gui.widgets.status_icon import supports_status_icon
from lutris.settings import read_setting
from lutris.util import proxy


def _is_system_dark_by_default():
    app = Gio.Application.get_default()
    return app.style_manager.is_dark_by_default


class SettingsPreferencesBox(BaseConfigBox):
    """A preferences page built from a list of option dicts, each of which is stored
    as a Lutris setting as soon as it is changed."""

    section_label = ""
    section_description = ""
    settings_options: list[dict[str, Any]] = []

    def build_settings_options(self):
        """Fills the page in; call this once the subclass is ready to have its widgets
        generated, since generating them reads the settings."""
        self.add(self.get_section_label(self.section_label))
        if self.section_description:
            self.add(self.get_description_label(self.section_description))

        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 0)

        gen = PreferencesWidgetGenerator(listbox)
        gen.changed.register(self.on_setting_changed)
        self.widget_generator = gen

        for option in self.settings_options:
            gen.generate_container(option)

            if gen.option_container:
                list_box_row = Gtk.ListBoxRow(visible=True)
                list_box_row.set_selectable(False)
                list_box_row.set_activatable(False)
                list_box_row.add(gen.option_container)
                listbox.add(list_box_row)

        gen.update_widgets()

    def on_setting_changed(self, option_key, new_value):
        settings.write_setting(option_key, new_value)


class InterfacePreferencesBox(SettingsPreferencesBox):
    section_label = _("Interface options")
    settings_options = [
        {
            "option": "hide_client_on_game_start",
            "label": _("Minimize client when a game is launched"),
            "type": "bool",
            "help": _("Minimize the Lutris window while playing a game; it will return when the game exits."),
        },
        {
            "option": "hide_text_under_icons",
            "label": _("Hide text under icons"),
            "type": "bool",
            "help": _("Removes the names from the Lutris window when in grid view, but not list view."),
        },
        {
            "option": "hide_badges_on_icons",
            "label": _("Hide badges on icons (Ctrl+p to toggle)"),
            "type": "bool",
            "accelerator": "<Primary>p",
            "help": _("Removes the platform and missing-game badges from icons in the Lutris window."),
        },
        {
            "option": "show_tray_icon",
            "label": _("Show Tray Icon"),
            "type": "bool",
            "available": supports_status_icon,
            "help": _(
                "Adds a Lutris icon to the tray, and prevents Lutris from exiting when the Lutris window is closed. "
                "You can still exit using the menu of the tray icon."
            ),
        },
        {
            "option": "discord_rpc",
            "label": _("Enable Discord Rich Presence for Available Games"),
            "type": "bool",
        },
        {
            "option": "preferred_theme",
            "type": "choice",
            "label": _("Theme"),
            "choices": [
                (_("System Default"), "default"),
                (_("Light"), "light"),
                (_("Dark"), "dark"),
            ],
            "default": "default",
            "help": _("Overrides Lutris's appearance to be light or dark."),
        },
    ]

    def __init__(self, accelerators):
        super().__init__()
        self.accelerators = accelerators
        self.build_settings_options()


class NetworkPreferencesBox(SettingsPreferencesBox):
    section_label = _("Proxy")
    section_description = _(
        "Lutris follows the <b>http_proxy</b>, <b>https_proxy</b> and <b>no_proxy</b> environment variables. "
        "Desktops that keep their proxy settings to themselves, such as KDE Plasma, do not set those, so the "
        "proxy has to be entered here instead. A proxy entered here overrides the environment, and is also "
        "passed on to the games Lutris launches."
    )
    settings_options = [
        {
            "option": "proxy_url",
            "type": "string",
            "label": _("Proxy server"),
            "placeholder": "http://proxy.example.com:8080",
            "help": _(
                "The proxy to send network requests through, as 'host:port' or a full URL such as "
                "'http://user:password@host:port'. Leave this empty to use the proxy from the environment."
            ),
        },
        {
            "option": "proxy_ignore_hosts",
            "type": "string",
            "label": _("Connect directly to"),
            "placeholder": "localhost, 127.0.0.1, .example.com",
            "conditional_on": "proxy_url",
            "help": _("Comma separated hosts and domains that should be reached directly, bypassing the proxy."),
        },
    ]

    def __init__(self):
        super().__init__()
        self.build_settings_options()

    def on_setting_changed(self, option_key, new_value):
        super().on_setting_changed(option_key, new_value)
        proxy.apply_to_environment()


class PreferencesWidgetGenerator(WidgetGenerator):
    """This generator adjusts the spacing of the wrappers and packs widgets on the
    right to get the interface preferences layout instead of the configuration one."""

    def get_setting(self, option_key: str, default: Any) -> Any:
        return read_setting(option_key, default=default)

    def create_wrapper_box(self, option: dict[str, Any], value: Any, default: Any) -> Gtk.Box | None:
        box = super().create_wrapper_box(option, value, default)
        if box:
            box.set_margin_top(12)
            box.set_margin_bottom(12)
            box.set_margin_right(12)
            box.set_margin_left(12)
        return box

    def _generate_string(self, option, value, default):
        entry = super()._generate_string(option, value, default)
        if entry:
            # These are packed against the right edge rather than filling the row, so they
            # need a width of their own to be usable.
            entry.set_width_chars(36)
        return entry

    def build_option_widget(
        self, option: dict[str, Any], widget: Gtk.Widget | None, no_label: bool = False, expand: bool = False
    ) -> Gtk.Widget | None:
        if no_label:
            return super().build_option_widget(option, widget, no_label=no_label, expand=expand)

        label = Gtk.Label(option["label"], visible=True, wrap=True)
        label.set_alignment(0, 0.5)
        if self.wrapper and widget:
            self.wrapper.pack_start(label, True, True, 0)
            self.wrapper.pack_end(widget, expand, expand, 0)
        return widget
