from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.scaled_image import ScaledImage
from lutris.services import SERVICES


class ServicesBox(BaseConfigBox):
    __gsignals__ = {
        "services-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.append(self.get_section_label(_("Enable integrations with game sources")))
        self.append(
            self.get_description_label(
                _("Access your game libraries from various sources. Changes require a restart to take effect.")
            )
        )
        self.frame = Gtk.Frame(visible=True)
        self.listbox = Gtk.ListBox(visible=True)
        self.frame.set_child(self.listbox)
        self.append(self.frame)

    def populate_services(self):
        for service_key in SERVICES:
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.set_child(self._get_service_box(service_key))
            self.listbox.append(list_box_row)

    def _get_service_box(self, service_key):
        box = Gtk.Box(
            spacing=12,
            margin_end=12,
            margin_start=12,
            margin_top=12,
            margin_bottom=12,
            height_request=32,
            visible=True,
        )
        in_games_view_key = service_key + "_in_games_view"
        service = SERVICES[service_key]
        is_active = settings.read_bool_setting(service_key, section="services")
        is_in_games_view = settings.read_bool_setting(in_games_view_key, default=True, section="services")

        icon = ScaledImage.get_runtime_icon_image(
            service.icon, service.id, scale_factor=self.get_scale_factor(), visible=True
        )
        box.append(icon)
        service_label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        label = Gtk.Label(visible=True)
        label.set_markup(f"<b>{service.name}</b>")
        label.set_halign(Gtk.Align.START)
        service_label_box.append(label)

        if service.description:
            desc_label = Gtk.Label(visible=True, wrap=True)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_text(service.description)
            service_label_box.append(desc_label)

        include_in_games_checkbox = Gtk.CheckButton(
            _("Show games from this source in the games view"),
            visible=is_active,
            active=is_in_games_view,
            halign=Gtk.Align.START,
        )
        include_in_games_checkbox.add_css_class("smallcheckbox")  # teeny tiny!
        include_in_games_checkbox.add_css_class("cuddledcheckbox")  # remove spacing around the checkbox
        include_in_games_checkbox.connect("toggled", self._on_include_in_games_change, in_games_view_key)
        service_label_box.append(include_in_games_checkbox)

        service_label_box.set_hexpand(True)
        service_label_box.set_vexpand(True)
        box.append(service_label_box)

        checkbox = Gtk.Switch(visible=True)
        checkbox.set_active(is_active)
        checkbox.connect("state-set", self._on_service_change, service_key, include_in_games_checkbox)
        checkbox.set_halign(Gtk.Align.CENTER)
        checkbox.set_valign(Gtk.Align.CENTER)
        checkbox.set_margin_start(6)
        checkbox.set_margin_end(6)
        box.append(checkbox)

        return box

    def _on_service_change(self, widget, state, setting_key, include_in_games_checkbox):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state, section="services")
        include_in_games_checkbox.set_visible(state)
        # if you can't view the games in their own service view, then
        # you need to see the min the name view, so make them visible there.
        include_in_games_checkbox.set_active(True)
        self.emit("services-changed")

    def _on_include_in_games_change(self, widget, setting_key):
        """Save a setting when an option is toggled"""
        state = widget.get_active()
        settings.write_setting(setting_key, state, section="services")
