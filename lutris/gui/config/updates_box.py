from gettext import gettext as _
from textwrap import dedent
from typing import Callable

from gi.repository import Gio, Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.dialogs import ErrorDialog, NoticeDialog
from lutris.gui.widgets.progress_box import ProgressInfo
from lutris.runtime import RuntimeUpdater
from lutris.services import get_enabled_services
from lutris.settings import UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_UNSUPPORTED


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
        hbox = Gtk.HBox(visible=True)
        stable_channel_radio_button = Gtk.RadioButton.new_from_widget(None)
        stable_channel_radio_button.set_active(update_channel == UPDATE_CHANNEL_STABLE)
        stable_channel_radio_button.set_margin_left(margin)
        stable_channel_radio_button.set_margin_top(margin)
        stable_channel_radio_button.set_margin_bottom(margin)
        stable_channel_radio_button.connect("toggled", self.on_update_channel_toggled, UPDATE_CHANNEL_STABLE)
        stable_channel_radio_button.show()

        hbox.pack_start(stable_channel_radio_button, False, False, margin)
        label = Gtk.Label(visible=True)
        label.set_markup(dedent(_("""
            <b>Stable</b>:
            Wine-GE updates are downloaded automatically and the latest version
            is always used unless overridden in the settings.
            This allows us to keep track of regressions more efficiently and provide
            fixes more reliably.
            """)))
        hbox.pack_start(label, False, True, 0)
        list_box.add(hbox)

        hbox = Gtk.HBox(visible=True)
        unsupported_channel_radio_button = Gtk.RadioButton.new_from_widget(stable_channel_radio_button)
        unsupported_channel_radio_button.set_active(update_channel == UPDATE_CHANNEL_UNSUPPORTED)
        unsupported_channel_radio_button.set_margin_left(margin)
        unsupported_channel_radio_button.set_margin_top(margin)
        unsupported_channel_radio_button.set_margin_bottom(margin)
        unsupported_channel_radio_button.connect("toggled", self.on_update_channel_toggled, UPDATE_CHANNEL_UNSUPPORTED)
        unsupported_channel_radio_button.show()
        hbox.pack_start(unsupported_channel_radio_button, False, False, margin)
        label = Gtk.Label(visible=True)
        label.set_markup(dedent(_("""
            <b>Self-maintained</b>:
            Wine updates are no longer delivered automatically and you have full responsibility
            of your wine versions.

            Please note that this mode is <b>fully unsupported</b>. In order to submit issues on Github
            or ask for help on Discord, switch back to the <b>Stable channel</b>.
            """)))
        hbox.pack_start(label, False, False, 0)
        list_box.add(hbox)

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
        update_media_button = Gtk.Button(_("Download missing media"), visible=True)
        update_media_button.connect("clicked", self.on_download_media_clicked)

        update_media_box = self.get_listed_widget_box("", update_media_button)
        frame.add(update_media_box)

    def on_download_media_clicked(self, widget):
        widget.hide()
        spinner = Gtk.Spinner(visible=True)
        spinner.start()

        self.trigger_media_load(self.get_toplevel())

    def trigger_media_load(self, parent: Gtk.Window) -> None:
        application = Gio.Application.get_default()
        if not application:
            return
        window = application.window
        if not window:
            return

        if window.download_queue.is_empty:
            services = list(get_enabled_services().items())
            if not services:
                return

            progress_info = ProgressInfo(None, _("Downloading %s media") % services[0][0])

            def load_media():
                nonlocal progress_info

                for name, service_type in services:
                    progress_info = ProgressInfo(None, _("Downloading %s media") % name)
                    service = service_type()
                    service.load_icons()

            def get_progress():
                return progress_info

            def load_media_cb(_result, _error):
                window.queue_draw()

            window.download_queue.start(load_media, get_progress, load_media_cb)
        else:
            ErrorDialog(_("Updates cannot begin while downloads are already underway."), parent=parent)

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
