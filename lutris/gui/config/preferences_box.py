from gettext import gettext as _

from gi.repository import Gio, Gtk

from lutris import settings
from lutris.gui.widgets.common import VBox


class PreferencesBox(VBox):
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

    def _get_section_label(self, text):
        label = Gtk.Label(visible=True)
        label.set_markup("<b>%s</b>" % text)
        label.set_alignment(0, 0.5)
        return label

    def __init__(self, accelerators):
        super().__init__(visible=True)
        self.accelerators = accelerators
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_right(80)
        self.set_margin_left(80)
        self.add(self._get_section_label(_("Interface options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 12)
        for setting_key, label in self.settings_options.items():
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(self._get_setting_box(setting_key, label))
            listbox.add(list_box_row)

    def _get_setting_box(self, setting_key, label):
        box = Gtk.Box(
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            visible=True
        )
        label = Gtk.Label(label, visible=True)
        label.set_alignment(0, 0.5)
        box.pack_start(label, True, True, 12)
        checkbox = Gtk.Switch(visible=True)
        if settings.read_setting(setting_key).lower() == "true":
            checkbox.set_active(True)
        checkbox.connect("state-set", self._on_setting_change, setting_key)

        if setting_key in self.settings_accelerators:
            key, mod = Gtk.accelerator_parse(self.settings_accelerators[setting_key])
            checkbox.add_accelerator("activate", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

        box.pack_start(checkbox, False, False, 12)
        return box

    def _on_setting_change(self, widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
        application = Gio.Application.get_default()

        if setting_key == "dark_theme":
            application.style_manager.is_config_dark = state
        elif setting_key == "show_tray_icon":
            if application.window.get_visible():
                application.set_tray_icon()

        self.get_toplevel().emit("settings-changed", setting_key)
