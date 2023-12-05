import os
from gettext import gettext as _
from typing import Callable

from gi.repository import Gio, Gtk

from lutris import settings
from lutris.api import get_default_runner_version_info, get_runtime_versions_date
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.dialogs import NoticeDialog
from lutris.runtime import RuntimeUpdater
from lutris.services.lutris import sync_media
from lutris.settings import UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_UNSUPPORTED
from lutris.util import system
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe, time_ago


class UpdatesBox(BaseConfigBox):

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Wine update channel")))

        update_channel = settings.read_setting("wine-update-channel", UPDATE_CHANNEL_STABLE)

        markup = _("<b>Stable</b>:\n"
                   "Wine-GE updates are downloaded automatically and the latest version "
                   "is always used unless overridden in the settings.\n"
                   "\n"
                   "This allows us to keep track of regressions more efficiently and provide "
                   "fixes more reliably.")
        stable_channel_radio_button = self._get_radio_button(markup,
                                                             active=update_channel == UPDATE_CHANNEL_STABLE,
                                                             group=None)

        markup = _("<b>Self-maintained</b>:\n"
                   "Wine updates are no longer delivered automatically and you have full responsibility "
                   "of your Wine versions.\n"
                   "\n"
                   "Please note that this mode is <b>fully unsupported</b>. In order to submit issues on Github "
                   "or ask for help on Discord, switch back to the <b>Stable channel</b>.")
        unsupported_channel_radio_button = self._get_radio_button(markup,
                                                                  active=update_channel == UPDATE_CHANNEL_UNSUPPORTED,
                                                                  group=stable_channel_radio_button)
        # Safer to connect these after the active property has been initialized on all radio buttons
        stable_channel_radio_button.connect("toggled", self.on_update_channel_toggled, UPDATE_CHANNEL_STABLE)
        unsupported_channel_radio_button.connect("toggled", self.on_update_channel_toggled, UPDATE_CHANNEL_UNSUPPORTED)

        wine_version_info = get_default_runner_version_info("wine")
        wine_version = f"{wine_version_info['version']}-{wine_version_info['architecture']}"
        if system.path_exists(os.path.join(settings.RUNNER_DIR, "wine", wine_version)):
            update_label_text = _(
                "Your wine version is up to date. Using: <b>%s</b>\n"
                "<i>Last checked %s.</i>"
            ) % (wine_version_info['version'], time_ago(get_runtime_versions_date()))
            update_button_text = _("Check again")
        elif not system.path_exists(os.path.join(settings.RUNNER_DIR, "wine")):
            update_label_text = _(
                "You don't have any Wine version installed.\n"
                "We recommend <b>%s</b>"
            ) % wine_version_info['version']
            update_button_text = _("Download %s") % wine_version_info['version']
        else:
            update_button_text = _(
                "You don't have the recommended Wine version: <b>%s</b>"
            ) % wine_version_info['version']
            update_button_text = _("Download %s") % wine_version_info['version']

        self.update_runnners_box = UpdateButtonBox(update_label_text,
                                                   update_button_text,
                                                   clicked=self.on_runners_update_clicked)

        self.pack_start(self._get_framed_options_list_box(
            [stable_channel_radio_button, unsupported_channel_radio_button]),
            False, False, 12)
        self.pack_start(self._get_framed_options_list_box(
            [self.update_runnners_box]),
            False, False, 12)

        self.add(self.get_section_label(_("Runtime updates")))
        self.add(self.get_description_label(
            _("Runtime components include DXVK, VKD3D and Winetricks.")
        ))
        self.update_runtime_box = UpdateButtonBox("",
                                                  _("Check for Updates"),
                                                  clicked=self.on_runtime_update_clicked)

        update_runtime_box = self.get_setting_box(
            "auto_update_runtime",
            _("Automatically Update the Lutris runtime"),
            default=True,
            extra_widget=self.update_runtime_box
        )
        self.pack_start(self._get_framed_options_list_box([update_runtime_box]), False, False, 12)
        self.add(self.get_section_label(_("Media updates")))
        self.update_media_box = UpdateButtonBox("",
                                                _("Download Missing Media"),
                                                clicked=self.on_download_media_clicked)
        self.pack_start(self._get_framed_options_list_box([self.update_media_box]), False, False, 12)

    def _get_radio_button(self, label_markup, active, group, margin=12):
        radio_button = Gtk.RadioButton.new_from_widget(group)
        radio_button.set_active(active)
        radio_button.set_margin_left(margin)
        radio_button.set_margin_right(margin)
        radio_button.set_margin_top(margin)
        radio_button.set_margin_bottom(margin)
        radio_button.set_visible(True)

        radio_button.set_label("")  # creates Gtk.Label child
        label = radio_button.get_child()
        label.set_markup(label_markup)
        label.set_margin_left(6)
        label.props.wrap = True
        return radio_button

    def _get_framed_options_list_box(self, items):
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        frame.add(list_box)

        for item in items:
            list_box.add(Gtk.ListBoxRow(child=item, visible=True, activatable=False))
        return frame

    def on_download_media_clicked(self, _widget):
        self.update_media_box.show_running_markup(_("<i>Checking for missing media...</i>"))
        AsyncCall(sync_media, self.on_media_updated)

    def on_media_updated(self, result, error):
        if error:
            self.update_media_box.show_error(error)
        elif not result:
            self.update_media_box.show_completion_markup(_("Nothing to update"))
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
            self.update_media_box.show_completion_markup(update_text)

            application = Gio.Application.get_default()
            if application and application.window:
                application.window.queue_draw()
        else:
            self.update_media_box.show_completion_markup(_("No new media found."))

    def on_runners_update_clicked(self, _widget):
        def get_updater():
            updater = RuntimeUpdater()
            updater.update_runners = True
            return updater

        self._trigger_updates(get_updater, self.update_runnners_box)

    def on_runtime_update_clicked(self, _widget):
        def get_updater():
            updater = RuntimeUpdater()
            updater.update_runtime = True
            return updater

        self._trigger_updates(get_updater, self.update_runtime_box)

    def _trigger_updates(self, updater_factory: Callable,
                         update_box: 'UpdateButtonBox') -> None:
        application = Gio.Application.get_default()
        if not application or not application.window:
            logger.error("No application or window found, how does this happen?")
            return

        window = application.window
        if window.download_queue.is_empty:
            updater = updater_factory()
            component_updaters = updater.create_component_updaters()
            if component_updaters:
                def on_complete(_result):
                    if len(component_updaters) == 1:
                        update_box.show_completion_markup(_("1 component has been updated."))
                    else:
                        update_box.show_completion_markup(
                            _("%d components have been updated.") % len(component_updaters))

                update_box.show_running_markup(_("<i>Checking for updates...</i>"))
                window.install_runtime_component_updates(component_updaters, updater,
                                                         completion_function=on_complete,
                                                         error_function=update_box.show_error)
            else:
                update_box.show_completion_markup(_("No updates are required at this time."))
        else:
            NoticeDialog(_("Updates cannot begin while downloads are already underway."),
                         parent=self.get_toplevel())

    def on_update_channel_toggled(self, checkbox, value):
        """Update setting when update channel is toggled
        """
        if not checkbox.get_active():
            return
        last_setting = settings.read_setting("wine-update-channel", UPDATE_CHANNEL_STABLE)
        if last_setting == UPDATE_CHANNEL_STABLE and value == UPDATE_CHANNEL_UNSUPPORTED:
            NoticeDialog(_(
                "Without the Wine-GE updates enabled, we can no longer provide support on Github and Discord."
            ), parent=self.get_toplevel())
        settings.write_setting("wine-update-channel", value)


class UpdateButtonBox(Gtk.Box):
    """A box containing a button to start updating something, with methods to show a result
    when done."""

    def __init__(self, label: str, button_label: str, clicked):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, margin=12, spacing=6, visible=True)

        self.label = Gtk.Label(visible=True, xalign=0)
        self.label.set_markup(label)
        self.pack_start(self.label, True, True, 0)

        self.button = Gtk.Button(button_label, visible=True)
        self.button.connect("clicked", clicked)
        self.pack_end(self.button, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.pack_end(self.spinner, False, False, 0)
        self.result_label = Gtk.Label()
        self.pack_end(self.result_label, False, False, 0)

    def show_running_markup(self, markup):
        self.button.hide()
        self.result_label.set_markup(markup)
        self.result_label.show()
        self.spinner.show()
        self.spinner.start()

    def show_completion_markup(self, markup):
        self.button.hide()
        self.result_label.show()
        self.spinner.stop()
        self.spinner.hide()
        self.result_label.set_markup(markup)

    def show_error(self, error):
        self.button.hide()
        self.result_label.show()
        self.spinner.stop()
        self.spinner.hide()
        self.result_label.set_markup("<b>Error:</b>%s" % gtk_safe(error))
