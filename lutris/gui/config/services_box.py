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
        self.add(self.get_section_label(_("Enable integrations with game sources")))
        self.add(
            self.get_description_label(
                _("Access your game libraries from various sources. Changes require a restart to take effect.")
            )
        )
        self.frame = Gtk.Frame(visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.listbox = Gtk.ListBox(visible=True)
        self.frame.add(self.listbox)
        self.pack_start(self.frame, False, False, 0)

    def populate_services(self):
        for service_key in SERVICES:
            list_box_row = Gtk.ListBoxRow(visible=True)
            list_box_row.set_selectable(False)
            list_box_row.set_activatable(False)
            list_box_row.add(self._get_service_box(service_key))
            self.listbox.add(list_box_row)

    def _get_service_box(self, service_key):
        box = Gtk.Box(
            spacing=12,
            margin_right=12,
            margin_left=12,
            margin_top=12,
            margin_bottom=12,
            visible=True,
        )
        service = SERVICES[service_key]

        icon = ScaledImage.get_runtime_icon_image(
            service.icon, service.id, scale_factor=self.get_scale_factor(), visible=True
        )
        box.pack_start(icon, False, False, 0)
        service_label_box = Gtk.VBox(visible=True)
        label = Gtk.Label(visible=True)
        label.set_markup(f"<b>{service.name}</b>")
        label.set_alignment(0, 0.5)
        service_label_box.pack_start(label, False, False, 0)

        desc_label = Gtk.Label(visible=True, wrap=True)
        desc_label.set_alignment(0, 0.5)
        desc_label.set_text(service.description)
        service_label_box.pack_start(desc_label, False, False, 0)
        box.pack_start(service_label_box, True, True, 0)

        checkbox = Gtk.Switch(visible=True)
        if settings.read_setting(service_key, section="services").lower() == "true":
            checkbox.set_active(True)
        checkbox.connect("state-set", self._on_service_change, service_key)
        alignment = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        alignment.show()
        alignment.add(checkbox)
        box.pack_start(alignment, False, False, 6)

        return box

    def _on_service_change(self, widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state, section="services")
        self.emit("services-changed")
