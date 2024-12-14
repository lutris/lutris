from gettext import gettext as _
from typing import Any, Dict, Optional

from gi.repository import Gio, Gtk

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
            "visible": supports_status_icon,
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
        self.add(self.get_section_label(_("Interface options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 0)

        gen = PreferencesWidgetGenerator()
        gen.changed.register(self.on_setting_changed)

        for option_dict in self.settings_options:
            value = settings.read_setting(option_dict["option"], default=None)
            gen.generate_widget(option_dict, value)

            if gen.wrapper:
                list_box_row = Gtk.ListBoxRow(visible=True)
                list_box_row.set_selectable(False)
                list_box_row.set_activatable(False)
                list_box_row.add(gen.wrapper)
                listbox.add(list_box_row)

    @staticmethod
    def on_setting_changed(option_key, new_value):
        settings.write_setting(option_key, new_value)


class PreferencesWidgetGenerator(WidgetGenerator):
    """This generator adjusts the spacing of the wrappers and packs widgets on the
    right to get the interface preferences layout instead of tje configuration one."""

    def __init__(self):
        super().__init__(read_setting)

    def create_wrapper_box(self, option: Dict[str, Any], value: Any, default: Any) -> Optional[Gtk.Box]:
        box = super().create_wrapper_box(option, value, default)
        if box:
            box.set_margin_top(12)
            box.set_margin_bottom(12)
            box.set_margin_right(12)
            box.set_margin_left(12)
        return box

    def build_option_widget(
        self, option: Dict[str, Any], widget: Optional[Gtk.Widget], no_label: bool = False, expand: bool = False
    ) -> Optional[Gtk.Widget]:
        if no_label:
            return super().build_option_widget(option, widget, no_label=no_label, expand=expand)

        label = Gtk.Label(option["label"], visible=True, wrap=True)
        label.set_alignment(0, 0.5)
        if self.wrapper and widget:
            self.wrapper.pack_start(label, True, True, 0)
            self.wrapper.pack_end(widget, expand, expand, 0)
        return widget
