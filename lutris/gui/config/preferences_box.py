from gettext import gettext as _

from gi.repository import Gtk

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


class UpdatePreferencesBox(BaseConfigBox):
    settings_options = {
        "auto_update_runtime": {
            "label": _("Automatically update the Lutris runtime"),
        },
        "auto_update_runners": {
            "label": _("Automatically update Wine"),
            "warning": _("<b>Warning</b> The Lutris Team does not support running games on old version of Wine.")
        }
    }

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Update options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 12)
        for setting_key, setting_option in self.settings_options.items():
            label = setting_option["label"]
            warning_markup = setting_option.get("warning")
            warning_condition = setting_option.get("warning_condition")

            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(self.get_setting_box(setting_key, label, warning_markup, warning_condition))
            listbox.add(list_box_row)
