from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk

from lutris import settings
from lutris.gui.config.base_config_box import BaseConfigBox
from lutris.gui.widgets.utils import ICON_SIZE, get_icon
from lutris.services import SERVICES


class ServicesBox(BaseConfigBox):
    __gsignals__ = {
        "services-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.add(self.get_section_label(_("Enable integrations with game sources")))
        self.add(self.get_description_label(
            _("Access your game libraries from various sources. "
              "Changes require a restart to take effect.")
        ))
        self.listbox = Gtk.ListBox(visible=True)
        self.pack_start(self.listbox, False, False, 12)
        GLib.idle_add(self.populate_services)

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
            margin_end=12,
            margin_start=12,
            margin_top=12,
            margin_bottom=12,
            visible=True,
        )
        service = SERVICES[service_key]
        pixbuf = get_icon(service.icon, icon_format="pixbuf", size=ICON_SIZE)
        if pixbuf:
            icon = Gtk.Image(visible=True)
            icon.set_from_pixbuf(pixbuf)
        else:
            icon = Gtk.Image.new_from_icon_name(service.id, Gtk.IconSize.DND)
            icon.show()
        box.pack_start(icon, False, False, 0)
        label = Gtk.Label(service.name, visible=True)
        label.set_xalign(0)
        box.pack_start(label, True, True, 0)

        checkbox = Gtk.Switch(visible=True)
        checkbox.set_valign(Gtk.Align.CENTER)
        if settings.read_setting(service_key,
                                 section="services").lower() == "true":
            checkbox.set_active(True)
        checkbox.connect("state-set", self._on_service_change, service_key)
        box.pack_start(checkbox, False, False, 6)

        return box

    def _on_service_change(self, widget, state, setting_key):
        """Save a setting when an option is toggled"""
        settings.write_setting(setting_key, state, section="services")
        self.emit("services-changed")
