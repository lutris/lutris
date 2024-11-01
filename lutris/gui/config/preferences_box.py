from gettext import gettext as _

from gi.repository import Gio, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.status_icon import supports_status_icon


def _is_system_dark_by_default():
    app = Gio.Application.get_default()
    return app.style_manager.is_dark_by_default


class InterfacePreferencesBox(BaseConfigBox):
    settings_options = [
        {"option": "hide_client_on_game_start", "label": _("Minimize client when a game is launched"), "type": "bool"},
        {"option": "hide_text_under_icons", "label": _("Hide text under icons"), "type": "bool"},
        {
            "option": "hide_badges_on_icons",
            "label": _("Hide badges on icons (Ctrl+p to toggle)"),
            "type": "bool",
            "accelerator": "<Primary>p",
        },
        {"option": "show_tray_icon", "label": _("Show Tray Icon"), "type": "bool", "visible": supports_status_icon},
        {
            "option": "light_theme",
            "label": _("Use Light Theme"),
            "type": "bool",
            "visible": lambda: _is_system_dark_by_default(),
        },
        {
            "option": "dark_theme",
            "label": _("Use Dark Theme"),
            "type": "bool",
            "visible": lambda: not _is_system_dark_by_default(),
        },
        {
            "option": "discord_rpc",
            "label": _("Enable Discord Rich Presence for Available Games"),
            "type": "bool",
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
        for option_dict in self.settings_options:
            visible = option_dict.get("visible")
            if visible is None:
                visible = True
            elif callable(visible):
                visible = visible()

            if visible:
                option = option_dict["option"]
                label = option_dict["label"]
                accelerator = option_dict.get("accelerator")

                list_box_row = Gtk.ListBoxRow(visible=True)
                list_box_row.set_selectable(False)
                list_box_row.set_activatable(False)
                list_box_row.add(self.get_setting_box(option, label, accelerator=accelerator))
                listbox.add(list_box_row)
