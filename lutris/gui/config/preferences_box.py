from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.status_icon import supports_status_icon


class InterfacePreferencesBox(BaseConfigBox):
    settings_options = {
        "hide_client_on_game_start": _("Minimize client when a game is launched"),
        "hide_text_under_icons": _("Hide text under icons"),
        "hide_badges_on_icons": _("Hide badges on icons (Ctrl+p to toggle)"),
        "show_tray_icon": _("Show Tray Icon"),
        "dark_theme": _("Use dark theme (requires dark theme variant for Gtk)"),
        "discord_rpc": _("Enable Discord Rich Presence for Available Games"),
    }

    settings_accelerators = {"hide_badges_on_icons": "<Primary>p"}

    settings_availability = {"show_tray_icon": supports_status_icon}

    def __init__(self, accelerators):
        super().__init__()
        self.accelerators = accelerators
        self.add(self.get_section_label(_("Interface options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 0)
        for setting_key, label in self.settings_options.items():
            available = setting_key not in self.settings_availability or self.settings_availability[setting_key]()

            if available:
                list_box_row = Gtk.ListBoxRow(visible=True)
                list_box_row.set_selectable(False)
                list_box_row.set_activatable(False)
                list_box_row.add(self.get_setting_box(setting_key, label))
                listbox.add(list_box_row)
