from gettext import gettext as _

from gi.repository import Gio, Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox


class InterfacePreferencesBox(BaseConfigBox):
    settings_options = {
        "hide_client_on_game_start": _("Minimize client when a game is launched"),
        "hide_text_under_icons": _("Hide text under icons"),
        "hide_badges_on_icons": _("Hide badges on icons (Ctrl+p to toggle)"),
        "show_tray_icon": _("Show Tray Icon"),
        "dark_theme": _("Use dark theme (requires dark theme variant for Gtk)"),
        "discord_rpc": _("Enable Discord Rich Presence for Available Games"),
    }

    settings_accelerators = {
        "hide_badges_on_icons": "<Primary>p"
    }

    def __init__(self, accelerators):
        super().__init__()
        self.accelerators = accelerators
        self.add(self.get_section_label(_("Interface options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 12)
        for setting_key, label in self.settings_options.items():
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(self.get_setting_box(setting_key, label))
            listbox.add(list_box_row)

    def _on_setting_change(self, widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
        application = Gio.Application.get_default()

        # That should be implemented in the
        # application's event handler for settings-changed.
        if setting_key == "dark_theme":
            application.style_manager.is_config_dark = state
        elif setting_key == "show_tray_icon":
            if application.window.get_visible():
                application.set_tray_icon()

        self.get_toplevel().emit("settings-changed", setting_key)
