from gettext import gettext as _
from textwrap import dedent
from typing import Callable

from gi.repository import Gio, Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.dialogs import ErrorDialog, NoticeDialog
from lutris.runtime import RuntimeUpdater
from lutris.services.lutris import sync_media
from lutris.settings import UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_UNSUPPORTED
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class UpdatesBox(BaseConfigBox):

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Wine update channel")))
        self.add(self.get_description_label(
            _("Keep Wine-GE up to date.")
        ))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.pack_start(frame, False, False, 12)

        list_box = Gtk.ListBox(visible=True)
        frame.add(list_box)

        update_channel = settings.read_setting("wine-update-channel", UPDATE_CHANNEL_STABLE)

        margin = 6
        stable_channel_radio_button = Gtk.RadioButton.new_from_widget(None)
        stable_channel_radio_button.set_active(update_channel == UPDATE_CHANNEL_STABLE)
        stable_channel_radio_button.set_margin_left(margin)
        stable_channel_radio_button.set_margin_top(margin)
        stable_channel_radio_button.set_margin_bottom(margin)
        stable_channel_radio_button.connect("toggled", self.on_update_channel_toggled, UPDATE_CHANNEL_STABLE)
        stable_channel_radio_button.show()
        stable_channel_radio_button.set_label("")  # creates Gtk.Label child
        label = stable_channel_radio_button.get_child()
        label.set_markup(dedent(_("""
            <b>Stable</b>:
            Wine-GE updates are downloaded automatically and the latest version
            is always used unless overridden in the settings.
            This allows us to keep track of regressions more efficiently and provide
            fixes more reliably.
            """)))
        label.set_margin_left(margin)
        list_box.add(stable_channel_radio_button)

        unsupported_channel_radio_button = Gtk.RadioButton.new_from_widget(stable_channel_radio_button)
        unsupported_channel_radio_button.set_active(update_channel == UPDATE_CHANNEL_UNSUPPORTED)
        unsupported_channel_radio_button.set_margin_left(margin)
        unsupported_channel_radio_button.set_margin_top(margin)
        unsupported_channel_radio_button.set_margin_bottom(margin)
        unsupported_channel_radio_button.connect("toggled", self.on_update_channel_toggled, UPDATE_CHANNEL_UNSUPPORTED)
        unsupported_channel_radio_button.show()
        unsupported_channel_radio_button.set_label("")  # creates Gtk.Label child
        label = unsupported_channel_radio_button.get_child()
        label.set_markup(dedent(_("""
            <b>Self-maintained</b>:
            Wine updates are no longer delivered automatically and you have full responsibility
            of your wine versions.

            Please note that this mode is <b>fully unsupported</b>. In order to submit issues on Github
            or ask for help on Discord, switch back to the <b>Stable channel</b>.
            """)))
        label.set_margin_left(margin)
        list_box.add(unsupported_channel_radio_button)

        self.add(self.get_section_label(_("Runtime updates")))
        self.add(self.get_description_label(
            _("Runtime components include DXVK, VKD3D and Winetricks.")
        ))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.pack_start(frame, False, False, 12)
        list_box = Gtk.ListBox(visible=True)
        frame.add(list_box)

        update_button = Gtk.Button(_("Check for updates"), halign=Gtk.Align.END, visible=True)
        update_button.connect("clicked", self.on_runtime_update_clicked)

        list_box_row = Gtk.ListBoxRow(visible=True, activatable=False)
        list_box_row.add(self.get_setting_box(
            "auto_update_runtime",
            _("Automatically Update the Lutris runtime"),
            default=True,
            extra_widget=update_button
        ))
        list_box.add(list_box_row)

        self.add(self.get_section_label(_("Media updates")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.pack_start(frame, False, False, 12)
        self.update_media_button = Gtk.Button(_("Download missing media"), visible=True)
        self.update_media_button.connect("clicked", self.on_download_media_clicked)

        update_media_box = self.get_listed_widget_box("", self.update_media_button)
        self.update_media_spinner = Gtk.Spinner()
        update_media_box.pack_end(self.update_media_spinner, False, False, 0)
        self.update_media_label = Gtk.Label()
        update_media_box.pack_end(self.update_media_label, False, False, 0)
        frame.add(update_media_box)

    def on_download_media_clicked(self, widget):
        widget.hide()
        self.update_media_label.set_markup(_("<i>Checking for missing media...</i>"))
        self.update_media_label.show()
        self.update_media_spinner.show()
        self.update_media_spinner.start()
        AsyncCall(sync_media, self.on_media_updated)

    def on_media_updated(self, result, error):
        self.update_media_spinner.stop()
        self.update_media_spinner.hide()
        if error:
            self.update_media_label.set_markup("<b>Error:</b>%s" % error)
        elif not result:
            self.update_media_label.set_markup(_("Nothing to update"))
        elif any(result.values()):
            update_text = _("Updated: ")
            names = {
                "banners": _("banner"),
                "icons": _("icon"),
                "covers": _("cover"),
            }
            for key, value in result.items():
                if value:
                    if not update_text.endswith(": "):
                        update_text += ", "
                    update_text += f"{value} {names[key]}{'s' if value > 1 else ''}"
            self.update_media_label.set_markup(update_text)
        else:
            self.update_media_label.set_markup(_("No new media found."))

    def _trigger_updates(self, parent: Gtk.Window,
                         updater_factory: Callable) -> None:
        application = Gio.Application.get_default()
        if application:
            window = application.window
            if window:
                if window.download_queue.is_empty:
                    updater = updater_factory(application)
                    component_updaters = updater.create_component_updaters()
                    if component_updaters:
                        window.install_runtime_component_updates(component_updaters, updater)
                    else:
                        ErrorDialog(_("No updates are required at this time."), parent=parent)
                else:
                    ErrorDialog(_("Updates cannot begin while downloads are already underway."), parent=parent)

    def trigger_runtime_updates(self, parent):
        def get_updater(application):
            updater = RuntimeUpdater(application.gpu_info)
            updater.update_runtime = True
            return updater

        self._trigger_updates(parent, get_updater)

    def trigger_runner_updates(self, parent):
        def get_updater(application):
            updater = RuntimeUpdater(application.gpu_info)
            updater.update_runners = True
            return updater

        self._trigger_updates(parent, get_updater)

    def on_runtime_update_clicked(self, widget):
        print(widget)

    def on_update_channel_toggled(self, _widget, value):
        """Update setting when update channel is toggled
        """
        last_setting = settings.read_setting("wine-update-channel", UPDATE_CHANNEL_STABLE)
        if last_setting == UPDATE_CHANNEL_STABLE and value == UPDATE_CHANNEL_UNSUPPORTED:
            NoticeDialog(_(
                "Without the Wine-GE updates enabled, we can no longer provide support on Github and Discord."
            ))
        settings.write_setting("wine-update-channel", value)
