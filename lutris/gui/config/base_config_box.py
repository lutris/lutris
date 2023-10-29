from gi.repository import Gtk

from lutris import settings
from lutris.gui.widgets.common import VBox


class BaseConfigBox(VBox):
    settings_options = {}
    settings_accelerators = {}

    def get_section_label(self, text):
        label = Gtk.Label(visible=True)
        label.set_markup("<b>%s</b>" % text)
        label.set_alignment(0, 0.5)
        label.set_margin_bottom(8)
        return label

    def get_description_label(self, text):
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

    def get_setting_box(self, setting_key, label):
        box = Gtk.Box(
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            visible=True
        )
        label = Gtk.Label(label, visible=True)
        label.set_alignment(0, 0.5)
        box.pack_start(label, True, True, 12)
        checkbox = Gtk.Switch(visible=True)

        if settings.read_setting(setting_key).lower() == "true":
            checkbox.set_active(True)
        checkbox.connect("state-set", self.on_setting_change, setting_key)

        if setting_key in self.settings_accelerators:
            key, mod = Gtk.accelerator_parse(self.settings_accelerators[setting_key])
            checkbox.add_accelerator("activate", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

        box.pack_start(checkbox, False, False, 12)
        return box

    def on_setting_change(self, widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
        self.get_toplevel().emit("settings-changed", state, setting_key)
