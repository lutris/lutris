import os
from gettext import gettext as _
from typing import Callable

from gi.repository import Gio, Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.dialogs import NoticeDialog
from lutris.runtime import RuntimeUpdater
from lutris.services.lutris import sync_media
from lutris.settings import UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_UNSUPPORTED
from lutris.util import system
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import gtk_safe
from lutris.util.wine.wine import WINE_DIR

LUTRIS_EXPERIMENTAL_FEATURES_ENABLED = os.environ.get("LUTRIS_EXPERIMENTAL_FEATURES_ENABLED") == "1"


class UpdatesBox(BaseConfigBox):
    def populate(self):
        self.add(self.get_section_label(_("Runtime updates")))
        self.add(self.get_description_label(_("Runtime components include DXVK, VKD3D and Winetricks.")))
        self.update_runtime_box = UpdateButtonBox("", _("Check for Updates"), clicked=self.on_runtime_update_clicked)

        update_runtime_box = self.get_setting_box(
            "auto_update_runtime",
            _("Automatically Update the Lutris runtime"),
            default=True,
            extra_widget=self.update_runtime_box,
        )
        self.pack_start(self._get_framed_options_list_box([update_runtime_box]), False, False, 0)
        self.add(self.get_section_label(_("Media updates")))
        self.update_media_box = UpdateButtonBox("", _("Download Missing Media"), clicked=self.on_download_media_clicked)
        self.pack_start(self._get_framed_options_list_box([self.update_media_box]), False, False, 0)

    def apply_wine_update_texts(self, completion_markup: str = "") -> None:
        label_markup, _button_label = self.get_wine_update_texts()
        self.update_runners_box.show_completion_markup(label_markup, completion_markup)

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

    def on_download_media_clicked(self, _widget):
        self.update_media_box.show_running_markup(_("<i>Checking for missing media...</i>"))
        AsyncCall(sync_media, self.on_media_updated)

    def on_media_updated(self, result, error):
        if error:
            self.update_media_box.show_error(error)
        elif not result:
            self.update_media_box.show_completion_markup("", _("Nothing to update"))
        elif any(result.values()):
            update_text = _("Updated: ")
            names = {
                ("banners", False): _("banner"),
                ("icons", False): _("icon"),
                ("covers", False): _("cover"),
                ("banners", True): _("banners"),
                ("icons", True): _("icons"),
                ("covers", True): _("covers"),
            }
            for key, value in result.items():
                if value:
                    if not update_text.endswith(": "):
                        update_text += ", "
                    update_text += f"{value} {names[(key, value > 1)]}"
            self.update_media_box.show_completion_markup("", update_text)
        else:
            self.update_media_box.show_completion_markup("", _("No new media found."))

    def _get_main_window(self):
        application = Gio.Application.get_default()
        if not application or not application.window:
            logger.error("No application or window found, how does this happen?")
            return
        return application.window

    def on_runners_update_clicked(self, _widget):
        window = self._get_main_window()
        if not window:
            return

        # Create runner dir if missing, to enable installing runner updates at all.
        if not system.path_exists(WINE_DIR):
            os.mkdir(WINE_DIR)

        updater = RuntimeUpdater(force=True)
        updater.update_runtime = False
        component_updaters = updater.create_component_updaters()
        if component_updaters:

            def on_complete(_result):
                self.apply_wine_update_texts()

            started = window.install_runtime_component_updates(
                component_updaters,
                updater,
                completion_function=on_complete,
                error_function=self.update_runners_box.show_error,
            )

            if started:
                self.update_runners_box.show_running_markup(_("<i>Downloading...</i>"))
            else:
                NoticeDialog(_("Updates are already being downloaded and installed."), parent=self.get_toplevel())
        else:
            self.apply_wine_update_texts(_("No updates are required at this time."))

    def on_runtime_update_clicked(self, _widget):
        def get_updater():
            updater = RuntimeUpdater(force=True)
            updater.update_runners = False
            return updater

        self._trigger_updates(get_updater, self.update_runtime_box)

    def _trigger_updates(self, updater_factory: Callable, update_box: "UpdateButtonBox") -> None:
        window = self._get_main_window()
        if not window:
            return

        updater = updater_factory()
        component_updaters = updater.create_component_updaters()
        if component_updaters:

            def on_complete(_result):
                component_names = [updater.name for updater in component_updaters]
                if len(component_names) == 1:
                    update_box.show_completion_markup("", _("%s has been updated.") % component_names[0])
                else:
                    update_box.show_completion_markup("", _("%s have been updated.") % ", ".join(component_names))

            started = window.install_runtime_component_updates(
                component_updaters, updater, completion_function=on_complete, error_function=update_box.show_error
            )

            if started:
                update_box.show_running_markup(_("<i>Checking for updates...</i>"))
            else:
                NoticeDialog(_("Updates are already being downloaded and installed."), parent=self.get_toplevel())
        else:
            update_box.show_completion_markup("", _("No updates are required at this time."))

    def on_update_channel_toggled(self, checkbox, value):
        """Update setting when update channel is toggled"""
        if not checkbox.get_active():
            return
        last_setting = settings.read_setting("wine-update-channel", UPDATE_CHANNEL_STABLE)
        if last_setting != UPDATE_CHANNEL_UNSUPPORTED and value == UPDATE_CHANNEL_UNSUPPORTED:
            NoticeDialog(
                _("Without the Wine-GE updates enabled, we can no longer provide support on Github and Discord."),
                parent=self.get_toplevel(),
            )
        settings.write_setting("wine-update-channel", value)


class UpdateButtonBox(Gtk.Box):
    """A box containing a button to start updating something, with methods to show a result
    when done."""

    def __init__(self, label: str, button_label: str, clicked: Callable[[Gtk.Widget], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, margin=12, spacing=6, visible=True)

        self.label = Gtk.Label(visible=True, xalign=0)
        self.label.set_markup(label)
        self.pack_start(self.label, True, True, 0)

        self.button = Gtk.Button(button_label, visible=True)
        self.button.connect("clicked", clicked)
        self.pack_end(self.button, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.pack_end(self.spinner, False, False, 0)
        self.result_label = Gtk.Label(wrap=True)
        self.pack_end(self.result_label, False, False, 0)

    def show_running_markup(self, markup: str) -> None:
        self.button.hide()
        self.result_label.set_markup(markup)
        self.result_label.show()
        self.spinner.show()
        self.spinner.start()

    def show_completion_markup(self, label_markup: str, completion_markup: str) -> None:
        self.button.hide()
        self.result_label.show()
        self.spinner.stop()
        self.spinner.hide()
        self.label.set_markup(label_markup)
        self.result_label.set_markup(completion_markup)

    def show_error(self, error: Exception) -> None:
        self.button.hide()
        self.result_label.show()
        self.spinner.stop()
        self.spinner.hide()
        self.result_label.set_markup("<b>Error:</b>%s" % gtk_safe(str(error)))
