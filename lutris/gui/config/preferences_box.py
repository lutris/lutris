from gettext import gettext as _

from gi.repository import Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox


class PreferencesBox(BaseConfigBox):
    settings_options = {
        "hide_client_on_game_start": _("Minimize client when a game is launched"),
        "hide_text_under_icons": _("Hide text under icons (requires restart)"),
        "show_tray_icon": _("Show Tray Icon (requires restart)"),
        "dark_theme": _("Use dark theme (requires dark theme variant for Gtk)")
    }

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Interface options")))
        listbox = Gtk.ListBox(visible=True)
        self.add(listbox)
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
        box.pack_start(checkbox, False, False, 12)
        return box

    def _on_setting_change(self, widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
