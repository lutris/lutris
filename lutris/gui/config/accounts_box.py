from gettext import gettext as _

from gi.repository import Gtk

from lutris import settings
from lutris.api import disconnect, read_user_info
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.config.updates_box import UpdateButtonBox
from lutris.gui.dialogs import ClientLoginDialog, QuestionDialog
from lutris.gui.widgets import EMPTY_NOTIFICATION_REGISTRATION
from lutris.services.lutris import sync_media
from lutris.util.jobs import AsyncCall
from lutris.util.library_sync import (
    LOCAL_LIBRARY_SYNCED,
    LOCAL_LIBRARY_SYNCING,
    LibrarySyncer,
    is_local_library_syncing,
)
from lutris.util.steam.config import STEAM_ACCOUNT_SETTING, get_steam_users
from lutris.util.strings import time_ago


class AccountsBox(BaseConfigBox):
    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Lutris")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        frame.get_style_context().add_class("info-frame")
        self.bullshit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        self.pack_start(frame, False, False, 0)

        self.lutris_options = self.get_lutris_options()
        self.bullshit_box.add(self.lutris_options)
        frame.add(self.bullshit_box)

        self.library_syncing_registration = EMPTY_NOTIFICATION_REGISTRATION
        self.library_synced_registration = EMPTY_NOTIFICATION_REGISTRATION

        self.sync_box = UpdateButtonBox(self.get_sync_box_label(), _("Sync Again"), clicked=self.on_sync_again_clicked)

        self.connect("realize", self.on_realize)
        self.connect("unrealize", self.on_unrealize)

        self.sync_frame = self._get_framed_options_list_box([self.sync_box])
        self.sync_frame.set_visible(settings.read_bool_setting("library_sync_enabled", True))

        self.pack_start(self.sync_frame, False, False, 0)

        self.add(self.get_section_label(_("Steam accounts")))
        self.add(
            self.get_description_label(
                _("Select which Steam account is used for Lutris integration and creating Steam shortcuts.")
            )
        )
        self.frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.frame.get_style_context().add_class("info-frame")
        self.pack_start(self.frame, False, False, 0)

        self.accounts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True)
        self.frame.add(self.accounts_box)

    def on_realize(self, _widget):
        self.library_syncing_registration = LOCAL_LIBRARY_SYNCING.register(self.on_local_library_syncing)
        self.library_synced_registration = LOCAL_LIBRARY_SYNCED.register(self.on_local_library_synced)
        if is_local_library_syncing():
            self.on_local_library_syncing()

    def on_unrealize(self, _widget) -> None:
        # The destroy signal never fires for this sub-widget, so we use
        # realize/unrealize for this instead.
        self.library_syncing_registration.unregister()
        self.library_synced_registration.unregister()

    def space_widget(self, widget, top=16, bottom=16):
        widget.set_margin_top(top)
        widget.set_margin_start(16)
        widget.set_margin_end(16)
        widget.set_margin_bottom(bottom)
        return widget

    def get_user_box(self):
        user_info = read_user_info()

        user_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, visible=True)

        label = Gtk.Label(visible=True)
        label.set_alignment(0, 0.5)
        if user_info:
            label.set_markup(_("Connected as <b>%s</b>") % user_info["username"])
        else:
            label.set_markup(_("Not connected"))
        self.space_widget(label)
        user_box.pack_start(label, True, True, 0)

        if user_info:
            button_text = _("Logout")
            button_handler = self.on_logout_clicked
        else:
            button_text = _("Login")
            button_handler = self.on_login_clicked
        button = Gtk.Button(button_text, visible=True)
        button.connect("clicked", button_handler)
        self.space_widget(button)
        user_box.pack_start(button, False, False, 0)
        return user_box

    def get_lutris_options(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True)
        box.add(self.get_user_box())

        sync_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, visible=True)
        sync_label = Gtk.Label(_("Keep your game library synced with Lutris.net"), visible=True)
        sync_switch = Gtk.Switch(visible=True)
        sync_switch.set_active(settings.read_bool_setting("library_sync_enabled", default=True))
        sync_switch.connect("state-set", self.on_sync_state_set)
        sync_box.pack_start(sync_label, False, False, 0)
        sync_box.pack_end(sync_switch, False, False, 0)
        self.space_widget(sync_box, bottom=0)
        box.add(sync_box)

        label = Gtk.Label(visible=True)
        label.set_alignment(0, 0.5)
        label.set_markup(
            _(
                "<i>This will send play time, last played, runner, platform \n"
                "and store information to the lutris website so you can \n"
                "sync this data on multiple devices</i>"
            )
        )
        self.space_widget(label, top=0)
        box.add(label)

        return box

    def populate_steam_accounts(self):
        main_radio_button = None
        active_steam_account = settings.read_setting(STEAM_ACCOUNT_SETTING)

        steam_users = get_steam_users()
        for account in steam_users:
            steamid64 = account["steamid64"]
            name = account.get("PersonaName") or f"#{steamid64}"
            radio_button = Gtk.RadioButton.new_with_label_from_widget(main_radio_button, name)
            self.space_widget(radio_button)
            radio_button.show()
            radio_button.set_active(active_steam_account == steamid64)
            radio_button.connect("toggled", self.on_steam_account_toggled, steamid64)
            self.accounts_box.pack_start(radio_button, True, True, 0)
            if not main_radio_button:
                main_radio_button = radio_button
        if not steam_users:
            self.accounts_box.pack_start(
                self.space_widget(Gtk.Label(_("No Steam account found"), visible=True)),
                True,
                True,
                0,
            )

    def rebuild_lutris_options(self):
        self.bullshit_box.remove(self.lutris_options)
        self.lutris_options.destroy()
        self.lutris_options = self.get_lutris_options()
        self.bullshit_box.add(self.lutris_options)

    def on_logout_clicked(self, _widget):
        disconnect()
        self.rebuild_lutris_options()

    def on_login_clicked(self, _widget):
        login_dialog = ClientLoginDialog(parent=self.get_toplevel())
        login_dialog.connect("connected", self.on_connect_response)

    def on_connect_response(self, _dialog, bliblu):
        self.rebuild_lutris_options()

    def on_sync_again_clicked(self, _button):
        AsyncCall(LibrarySyncer().sync_local_library, None, force=True)

    def on_local_library_syncing(self):
        self.sync_box.show_running_markup(_("<i>Syncing library...</i>"))

    def on_local_library_synced(self):
        self.sync_box.show_completion_markup(self.get_sync_box_label(), "")
        AsyncCall(sync_media, None)

    def get_sync_box_label(self):
        synced_at = settings.read_setting("last_library_sync_at")
        if synced_at:
            return _("<i>Last synced %s.</i>") % time_ago(int(synced_at))

        return ""

    def on_steam_account_toggled(self, radio_button, steamid64):
        """Handler for switching the active Steam account."""
        settings.write_setting(STEAM_ACCOUNT_SETTING, steamid64)

    def on_sync_state_set(self, switch, state):
        if not settings.read_setting("last_library_sync_at"):
            sync_warn_dialog = QuestionDialog(
                {
                    "title": _("Synchronize library?"),
                    "question": _("Enable library sync and run a full sync with lutris.net?"),
                }
            )
            if sync_warn_dialog.result == Gtk.ResponseType.YES:
                AsyncCall(LibrarySyncer().sync_local_library, None)
            else:
                return

        self.on_setting_change(switch, state, "library_sync_enabled")
        self.sync_frame.set_visible(state)
