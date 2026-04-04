from gettext import gettext as _
from typing import Any

from gi.repository import Gio, Gtk  # type: ignore

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.widget_generator import WidgetGenerator
from lutris.gui.widgets.status_icon import supports_status_icon
from lutris.settings import read_setting


def _is_system_dark_by_default():
    app = Gio.Application.get_default()
    return app.style_manager.is_dark_by_default


class InterfacePreferencesBox(BaseConfigBox):
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

        self.append(self.get_section_label(_("Interface options")))
        frame = Gtk.Frame(visible=True)
        listbox = Gtk.ListBox(visible=True)
        frame.set_child(listbox)
        self.append(frame)

        gen = PreferencesWidgetGenerator(listbox)
        gen.changed.register(self.on_setting_changed)
        self.widget_generator = gen

        for option in self.settings_options:
            gen.generate_container(option)

            if gen.option_container:
                list_box_row = Gtk.ListBoxRow(visible=True)
                list_box_row.set_selectable(False)
                list_box_row.set_activatable(False)
                list_box_row.set_child(gen.option_container)
                listbox.append(list_box_row)

        gen.update_widgets()

    def on_setting_changed(self, option_key, new_value):
        settings.write_setting(option_key, new_value)


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
            box.set_margin_end(12)
            box.set_margin_start(12)
        return box

    def build_option_widget(
        self, option: dict[str, Any], widget: Gtk.Widget | None, no_label: bool = False, expand: bool = False
    ) -> Gtk.Widget | None:
        if no_label:
            return super().build_option_widget(option, widget, no_label=no_label, expand=expand)

        label = Gtk.Label(option["label"], visible=True, wrap=True)
        label.set_halign(Gtk.Align.START)
        if self.wrapper and widget:
            label.set_hexpand(True)
            label.set_vexpand(True)
            self.wrapper.append(label)
            if expand:
                widget.set_hexpand(True)
                widget.set_vexpand(True)
            self.wrapper.append(widget)
        return widget
