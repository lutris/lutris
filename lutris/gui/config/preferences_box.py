from gettext import gettext as _
from typing import Callable

from gi.repository import Gio, Gtk

from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.widgets.progress_box import ProgressInfo
from lutris.runtime import RuntimeUpdater
from lutris.services import get_enabled_services


def trigger_media_load(parent: Gtk.Window) -> None:
    application = Gio.Application.get_default()
    if application:
        window = application.window
        if window:
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


def _trigger_updates(parent: Gtk.Window,
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


def trigger_runtime_updates(parent):
    def get_updater(application):
        updater = RuntimeUpdater(application.gpu_info)
        updater.update_runtime = True
        return updater

    _trigger_updates(parent, get_updater)


def trigger_runner_updates(parent):
    def get_updater(application):
        updater = RuntimeUpdater(application.gpu_info)
        updater.update_runners = True
        return updater

    _trigger_updates(parent, get_updater)


class InterfacePreferencesBox(BaseConfigBox):
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

    def __init__(self, accelerators):
        super().__init__()
        self.accelerators = accelerators
        self.add(self.get_section_label(_("Interface options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True)
        frame.add(listbox)
        self.pack_start(frame, False, False, 12)
        for setting_key, label in self.settings_options.items():
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(self.get_setting_box(setting_key, label))
            listbox.add(list_box_row)


class UpdatePreferencesBox(BaseConfigBox):
    settings_options = {
        "auto_update_runtime": {
            "label": _("Automatically Update the Lutris runtime"),
            "default": True,
            "update_function": trigger_runtime_updates
        },
        "auto_update_runners": {
            "label": _("Automatically Update Wine"),
            "default": True,
            "update_function": trigger_runner_updates,
            "warning":
                _("<b>Warning</b> The Lutris Team does not support running games on old version of Wine.\n"
                  "<i>Automatic Wine updates are strongly recommended.</i>"),
            "warning_condition": lambda active: not active
        }
    }

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Update options")))
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        frame.add(listbox)
        self.pack_start(frame, False, False, 12)

        update_media_button = Gtk.Button("Download Now", visible=True)
        update_media_button.connect("clicked", self.on_download_media_clicked)

        update_media_box = self.get_listed_widget_box(_("Download missing media"), update_media_button)

        list_box_row = Gtk.ListBoxRow(visible=True, activatable=False)
        list_box_row.add(update_media_box)
        listbox.add(list_box_row)

        for setting_key, setting_option in self.settings_options.items():
            label = setting_option["label"]
            default = setting_option.get("default") or False
            warning_markup = setting_option.get("warning")
            warning_condition = setting_option.get("warning_condition")
            update_function = setting_option.get("update_function")

            if update_function:
                def on_update_now_clicked(_widget, func):
                    func(self.get_toplevel())

                update_button = Gtk.Button(_("Update Now"), halign=Gtk.Align.END, visible=True)
                update_button.connect("clicked", on_update_now_clicked, update_function)
            else:
                update_button = None

            list_box_row = Gtk.ListBoxRow(visible=True, activatable=False)
            list_box_row.add(self.get_setting_box(setting_key, label, default=default,
                                                  warning_markup=warning_markup,
                                                  warning_condition=warning_condition,
                                                  extra_widget=update_button))
            listbox.add(list_box_row)

    def on_download_media_clicked(self, _widget):
        trigger_media_load(self.get_toplevel())
