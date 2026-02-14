from typing import Callable, Optional

from gi.repository import Gtk

from lutris import settings
from lutris.gui.config.widget_generator import WidgetWarningMessageBox
from lutris.gui.widgets.common import VBox


class BaseConfigBox(VBox):
    settings_accelerators = {}

    def __init__(self):
        super().__init__(visible=True, spacing=12)
        self.accelerators = None
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_right(80)
        self.set_margin_left(80)

    def get_section_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(visible=True)
        label.set_markup("<b>%s</b>" % text)
        label.set_alignment(0, 0.5)
        return label

    def get_description_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(visible=True)
        label.set_markup("%s" % text)
        label.set_line_wrap(True)
        label.set_alignment(0, 0.5)
        return label

    def _get_framed_options_list_box(self, items):
        frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)

        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        frame.add(list_box)

        for item in items:
            list_box.add(Gtk.ListBoxRow(child=item, visible=True, activatable=False))
        return frame

    def get_setting_box(
        self,
        setting_key: str,
        label: str,
        default: bool = False,
        accelerator: str = None,
        warning_markup: str = None,
        warning_condition: Callable[[bool], bool] = None,
        extra_widget: Gtk.Widget = None,
    ) -> Gtk.Box:
        setting_value = settings.read_bool_setting(setting_key, default=default)

        if not warning_markup and not extra_widget:
            box = self._get_inner_settings_box(setting_key, setting_value, label, accelerator)
        else:
            if warning_markup:

                def update_warning(active):
                    visible = warning_condition(active) if bool(warning_condition) else active
                    warning_box.show_markup(warning_markup if visible else None)

                warning_box = WidgetWarningMessageBox("dialog-warning", margin_left=0, margin_right=0, margin_bottom=0)
                update_warning(setting_value)
                inner_box = self._get_inner_settings_box(
                    setting_key, setting_value, label, accelerator, margin=0, when_setting_changed=update_warning
                )
            else:
                warning_box = None
                inner_box = self._get_inner_settings_box(
                    setting_key,
                    setting_value,
                    label,
                    accelerator,
                    margin=0,
                )

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True)
            box.pack_start(inner_box, False, False, 0)
            if warning_box:
                box.pack_start(warning_box, False, False, 0)
            if extra_widget:
                box.pack_start(extra_widget, False, False, 0)

        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_left(12)
        box.set_margin_right(12)
        return box

    def _get_inner_settings_box(
        self,
        setting_key: str,
        setting_value: bool,
        label: str,
        accelerator: str = None,
        margin: int = 12,
        when_setting_changed: Callable[[bool], None] = None,
    ):
        checkbox = Gtk.Switch(visible=True, valign=Gtk.Align.CENTER)
        checkbox.set_active(setting_value)
        checkbox.connect("state-set", self.on_setting_change, setting_key, when_setting_changed)

        if accelerator:
            key, mod = Gtk.accelerator_parse(accelerator)
            checkbox.add_accelerator("activate", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

        return self.get_listed_widget_box(label, checkbox, margin=margin)

    def get_listed_widget_box(self, label: str, widget: Gtk.Widget, margin: int = 12) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin=margin, visible=True)
        label = Gtk.Label(label=label, visible=True, wrap=True)
        label.set_alignment(0, 0.5)
        box.pack_start(label, True, True, 0)
        box.pack_end(widget, False, False, 0)
        return box

    def on_setting_change(
        self, _widget, state: bool, setting_key: str, when_setting_changed: Optional[Callable[[bool], None]] = None
    ) -> None:
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
        if when_setting_changed:
            when_setting_changed(state)
