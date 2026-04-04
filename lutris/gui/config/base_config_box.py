from collections.abc import Callable

from gi.repository import Gtk

from lutris import settings
from lutris.gui.config.widget_generator import WidgetWarningMessageBox
from lutris.gui.widgets.common import VBox


class BaseConfigBox(VBox):
    settings_accelerators = {}

    def __init__(self):
        super().__init__(visible=True, spacing=12)
        self.shortcut_controller = None
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_end(80)
        self.set_margin_start(80)

    def get_section_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(visible=True)
        label.set_markup("<b>%s</b>" % text)
        label.set_halign(Gtk.Align.START)
        return label

    def get_description_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(visible=True)
        label.set_markup("%s" % text)
        label.set_wrap(True)
        label.set_halign(Gtk.Align.START)
        return label

    def _get_framed_options_list_box(self, items):
        frame = Gtk.Frame(visible=True)

        list_box = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        frame.set_child(list_box)

        for item in items:
            list_box.append(Gtk.ListBoxRow(child=item, visible=True, activatable=False))
        return frame

    def get_setting_box(
        self,
        setting_key: str,
        label: str,
        default: bool = False,
        accelerator: str | None = None,
        warning_markup: str | None = None,
        warning_condition: Callable[[bool], bool] | None = None,
        extra_widget: Gtk.Widget | None = None,
    ) -> Gtk.Box:
        setting_value = settings.read_bool_setting(setting_key, default=default)

        if not warning_markup and not extra_widget:
            box = self._get_inner_settings_box(setting_key, setting_value, label, accelerator)
        else:
            if warning_markup:

                def update_warning(active):
                    visible = warning_condition(active) if bool(warning_condition) else active
                    warning_box.show_markup(warning_markup if visible else None)

                warning_box = WidgetWarningMessageBox("dialog-warning", margin_start=0, margin_end=0, margin_bottom=0)
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
            box.append(inner_box)
            if warning_box:
                box.append(warning_box)
            if extra_widget:
                box.append(extra_widget)

        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        return box

    def _get_inner_settings_box(
        self,
        setting_key: str,
        setting_value: bool,
        label: str,
        accelerator: str | None = None,
        margin: int = 12,
        when_setting_changed: Callable[[bool], None] | None = None,
    ):
        checkbox = Gtk.Switch(visible=True, valign=Gtk.Align.CENTER)
        checkbox.set_active(setting_value)
        checkbox.connect("state-set", self.on_setting_change, setting_key, when_setting_changed)

        if accelerator and self.shortcut_controller:
            trigger = Gtk.ShortcutTrigger.parse_string(accelerator)
            if trigger:
                action = Gtk.CallbackAction.new(lambda _w, _a, cb=checkbox: cb.activate() or True)
                self.shortcut_controller.add_shortcut(Gtk.Shortcut(trigger=trigger, action=action))

        return self.get_listed_widget_box(label, checkbox, margin=margin)

    def get_listed_widget_box(self, label: str, widget: Gtk.Widget, margin: int = 12) -> Gtk.Box:
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            visible=True,
        )
        label = Gtk.Label(label=label, visible=True, wrap=True)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_vexpand(True)
        box.append(label)
        box.append(widget)
        return box

    def on_setting_change(
        self, _widget, state: bool, setting_key: str, when_setting_changed: Callable[[bool], None] | None = None
    ) -> None:
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state)
        if when_setting_changed:
            when_setting_changed(state)
