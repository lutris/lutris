from gettext import gettext as _

from gi.repository import Gio, Gtk

from lutris import settings
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
            "option": "discord_rpc",
            "label": _("Enable Discord Rich Presence for Available Games"),
            "type": "bool",
        },
        {
            "option": "preferred_theme",
            "type": "choice",
            "label": "Theme",
            "choices": [
                (_("System Default"), "default"),
                (_("Light"), "light"),
                (_("Dark"), "dark"),
            ],
            "default": "default",
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
                option_type = option_dict["type"]

                if option_type == "bool":
                    widget = self._create_bool_setting(**option_dict)
                elif option_type == "choice":
                    widget = self._create_choice_setting(**option_dict)
                else:
                    raise ValueError("Unsupported widget type %s" % option_type)

                list_box_row = Gtk.ListBoxRow(visible=True)
                list_box_row.set_selectable(False)
                list_box_row.set_activatable(False)
                list_box_row.add(widget)
                listbox.add(list_box_row)

    def _create_bool_setting(self, option, label, accelerator=None, **kwargs):
        return self.get_setting_box(option, label, accelerator=accelerator)

    # ComboBox
    def _create_choice_setting(self, option, choices, label, default=None, **kwargs):
        """Generate a combobox (drop-down menu)."""

        @staticmethod
        def _on_combobox_scroll(_event):
            """Prevents users from accidentally changing configuration values
            while scrolling down dialogs.
            """
            combobox.stop_emission_by_name("scroll-event")
            return False

        def on_combobox_change(_widget):
            """Action triggered on combobox 'changed' signal."""
            list_store = combobox.get_model()
            active = combobox.get_active()
            option_value = None
            if active < 0:
                if combobox.get_has_entry():
                    option_value = combobox.get_child().get_text()
            else:
                option_value = list_store[active][1]
            settings.write_setting(option, option_value)

        @staticmethod
        def _expand_combobox_choices():
            expanded = []
            has_value = False
            for ch in choices:
                if isinstance(ch, str):
                    ch = (ch, ch)
                if ch[1] == value:
                    has_value = True
                expanded.append(ch)
            if not has_value and value:
                expanded.insert(0, (value + " (invalid)", value))
            return expanded

        value = settings.read_setting(option, default=default)

        expanded = _expand_combobox_choices()
        liststore = Gtk.ListStore(str, str)
        for choice in expanded:
            liststore.append(choice)

        combobox = Gtk.ComboBox.new_with_model(liststore)
        cell = Gtk.CellRendererText()
        combobox.pack_start(cell, True)
        combobox.add_attribute(cell, "text", 0)
        combobox.set_id_column(1)
        combobox.set_active_id(value)

        combobox.connect("changed", on_combobox_change)
        combobox.connect("scroll-event", _on_combobox_scroll)
        combobox.set_valign(Gtk.Align.CENTER)
        combobox.show()
        return self.get_listed_widget_box(label, combobox)
