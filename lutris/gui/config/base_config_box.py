from typing import Callable

from gi.repository import Gtk

from lutris import settings
from lutris.gui.config.boxes import UnderslungMessageBox
from lutris.gui.widgets.common import VBox


class BaseConfigBox(VBox):
    settings_accelerators = {}

    def get_section_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(visible=True)
        label.set_markup("<b>%s</b>" % text)
        label.set_alignment(0, 0.5)
        label.set_margin_bottom(8)
        return label

    def get_description_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(visible=True)
        label.set_markup("%s" % text)
        label.set_line_wrap(True)
        label.set_alignment(0, 0.5)
        return label

    def __init__(self):
        super().__init__(visible=True)
        self.accelerators = None
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_right(80)
        self.set_margin_left(80)

    def get_setting_box(self, setting_key: str, label: str,
                        default: bool = False,
                        warning_markup: str = None,
                        warning_condition: Callable[[bool], bool] = None) -> Gtk.Box:

        setting_value = settings.read_bool_setting(setting_key, default=default)

        if not warning_markup:
            box = self._get_inner_settings_box(setting_key, setting_value, label, self.on_setting_change)
        else:
            warning = UnderslungMessageBox("dialog-warning")

            def update_warning(state):
                visible = warning_condition(state) if warning_condition else state
                warning.show_markup(warning_markup if visible else None)

            def handle_setting_change(widget, state, key):
                self.on_setting_change(widget, state, key)
                update_warning(state)

            update_warning(setting_value)
            inner_box = self._get_inner_settings_box(setting_key, setting_value, label, handle_setting_change)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True)
            box.pack_start(inner_box, False, False, 0)
            box.pack_start(warning, False, False, 0)

        box.set_margin_top(12)
        box.set_margin_bottom(12)
        return box

    def _get_inner_settings_box(self, setting_key, setting_value, label, change_handler):
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            visible=True
        )
        label = Gtk.Label(label, visible=True)
        label.set_alignment(0, 0.5)
        box.pack_start(label, True, True, 12)
        checkbox = Gtk.Switch(visible=True)
        checkbox.set_active(setting_value)
        checkbox.connect("state-set", change_handler, setting_key)

        if setting_key in self.settings_accelerators:
            key, mod = Gtk.accelerator_parse(self.settings_accelerators[setting_key])
            checkbox.add_accelerator("activate", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

        box.pack_start(checkbox, False, False, 12)
        return box

    def on_setting_change(self, _widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
        self.get_toplevel().emit("settings-changed", state, setting_key)
