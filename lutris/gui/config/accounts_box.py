from gettext import gettext as _

from gi.repository import Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.util.jobs import AsyncCall
from lutris.util.library_sync import sync_local_library
from lutris.util.steam.config import STEAM_ACCOUNT_SETTING, get_steam_users


class AccountsBox(BaseConfigBox):
    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Lutris")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        frame.get_style_context().add_class("info-frame")
        self.pack_start(frame, False, False, 0)

        frame.add(self.get_lutris_options())

        self.add(self.get_section_label(_("Steam accounts")))
        self.add(
            self.get_description_label(
                _(
                    "Select which Steam account is used for Lutris integration and creating Steam shortcuts."
                )
            )
        )
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        frame.get_style_context().add_class("info-frame")
        self.pack_start(frame, False, False, 0)

        self.accounts_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True
        )
        frame.add(self.accounts_box)

    def space_widget(self, widget, top=16, bottom=16):
        widget.set_margin_top(top)
        widget.set_margin_start(16)
        widget.set_margin_bottom(bottom)

    def get_lutris_options(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True)
        checkbutton = Gtk.CheckButton.new_with_label(
            _("Keep your game library synced with Lutris.net")
        )
        checkbutton.show()
        self.space_widget(checkbutton, bottom=0)
        box.add(checkbutton)

        label = Gtk.Label(visible=True)
        label.set_alignment(0, 0.5)
        label.set_markup(
            _(
                "<i>This will send play time, last played, runner, platform \n"
                "and store information to the lutris website so you can \n"
                "sync this data on multiple devices (this is currently being implemented)</i>"
            )
        )
        self.space_widget(label, top=0)
        box.add(label)

        button = Gtk.Button(_("Sync now"), visible=True)
        button.connect("clicked", self.on_sync_clicked)
        self.space_widget(button)
        box.add(button)

        return box

    def populate_accounts(self):
        main_radio_button = None
        active_steam_account = settings.read_setting(STEAM_ACCOUNT_SETTING)

        steam_users = get_steam_users()
        for account in steam_users:
            steamid64 = account["steamid64"]
            name = account.get("PersonaName") or f"#{steamid64}"
            radio_button = Gtk.RadioButton.new_with_label_from_widget(
                main_radio_button, name
            )
            self.space_widget(radio_button)
            radio_button.show()
            radio_button.set_active(active_steam_account == steamid64)
            radio_button.connect("toggled", self.on_steam_account_toggled, steamid64)
            self.accounts_box.pack_start(radio_button, True, True, 0)
            if not main_radio_button:
                main_radio_button = radio_button
        if not steam_users:
            self.accounts_box.pack_start(
                Gtk.Label(_("No Steam account found"), visible=True), True, True, 0
            )

    def on_steam_account_toggled(self, radio_button, steamid64):
        """Handler for switching the active Steam account."""
        settings.write_setting(STEAM_ACCOUNT_SETTING, steamid64)

    def on_sync_clicked(self, button):

        def sync_cb(result, error):
            button.set_sensitive(True)

        button.set_sensitive(False)
        AsyncCall(sync_local_library, sync_cb)
