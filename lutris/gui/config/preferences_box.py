from gettext import gettext as _
from typing import Any

from gi.repository import Gio, Gtk  # type: ignore

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.widget_generator import WidgetGenerator
from lutris.gui.widgets.artwork_source import ArtworkSourceButtons
from lutris.gui.widgets.status_icon import supports_status_icon
from lutris.settings import read_setting
from lutris.util.jobs import AsyncCall


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
            "option": "steamgriddb_api_key",
            "label": _("SteamGridDB API key"),
            "type": "string",
            "help": _(
                "Required when SteamGridDB is selected as the artwork source. "
                "The key is stored in your local Lutris configuration file. "
                "Get a key at https://www.steamgriddb.com/profile/preferences."
            ),
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

        gen = PreferencesWidgetGenerator(listbox)
        gen.changed.register(self.on_setting_changed)
        self.widget_generator = gen

        row = Gtk.ListBoxRow(visible=True, selectable=False, activatable=False)
        box = Gtk.Box(visible=True, spacing=12, margin=12)
        box.pack_start(Gtk.Label(label=_("Artwork source"), visible=True, xalign=0), True, True, 0)
        source = settings.read_setting("artwork_source", default="lutris")
        buttons = ArtworkSourceButtons(
            [(_("Lutris.net"), "lutris"), (_("SteamGridDB"), "steamgriddb")],
            source if source in ("lutris", "steamgriddb") else "lutris",
            self.on_artwork_source_changed,
        )
        box.pack_end(buttons, False, False, 0)
        buttons.show_all()
        row.add(box)
        listbox.add(row)

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

    def on_artwork_source_changed(self, source):
        from lutris.artwork import ARTWORK_LOCK, refresh_artwork

        with ARTWORK_LOCK:
            settings.write_setting("artwork_source", source)
        AsyncCall(refresh_artwork, None, force=True, inherited_only=True)
        if source == "steamgriddb" and not (settings.read_setting("steamgriddb_api_key") or "").strip():
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=_("Add a SteamGridDB API key in Preferences."),
            )
            dialog.run()
            dialog.destroy()


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

    def build_option_widget(
        self, option: dict[str, Any], widget: Gtk.Widget | None, no_label: bool = False, expand: bool = False
    ) -> Gtk.Widget | None:
        if option["option"] == "steamgriddb_api_key" and isinstance(widget, Gtk.Entry):
            widget.set_visibility(False)
            widget.set_input_purpose(Gtk.InputPurpose.PASSWORD)

        if no_label:
            return super().build_option_widget(option, widget, no_label=no_label, expand=expand)

        label = Gtk.Label(label=option["label"], visible=True, wrap=True)
        label.set_alignment(0, 0.5)
        if self.wrapper and widget:
            self.wrapper.pack_start(label, True, True, 0)
            self.wrapper.pack_end(widget, expand, expand, 0)
        return widget
