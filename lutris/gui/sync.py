from gi.repository import Gtk, GLib, Gio
from lutris.gui.widgets.utils import get_icon
from lutris.gui.dialogs import NoticeDialog
from lutris.services import get_services
from lutris.settings import read_setting, write_setting
from lutris.util.jobs import AsyncCall


class ServiceSyncRow(Gtk.Box):

    def __init__(self, service, dialog):
        super().__init__()
        self.set_spacing(20)

        self.identifier = service.__name__.split('.')[-1]
        name = service.NAME

        icon = get_icon(self.identifier)
        self.pack_start(icon, False, False, 0)

        label = Gtk.Label()
        label.set_xalign(0)
        label.set_markup("<b>{}</b>".format(name))
        self.pack_start(label, True, True, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pack_start(actions, False, False, 0)

        if hasattr(service, "connect"):
            self.connect_button = Gtk.Button()
            self.connect_button.connect('clicked', self.on_connect_clicked, service)
            self._connect_button_toggle(service.is_connected())
            actions.pack_start(self.connect_button, False, False, 0)

        if hasattr(service, "sync_with_lutris"):
            self.sync_switch = Gtk.Switch()
            self.sync_switch.set_tooltip_text("Sync when Lutris starts")
            self.sync_switch.props.valign = Gtk.Align.CENTER
            self.sync_switch.connect('notify::active', self.on_switch_changed)

            if read_setting('sync_at_startup', self.identifier) == 'True':
                self.sync_switch.set_state(True)
            actions.pack_start(self.sync_switch, False, False, 0)

            self.sync_button = Gtk.Button("Sync")
            self.sync_button.set_tooltip_text("Sync now")
            self.sync_button.connect('clicked', self.on_sync_button_clicked, service.sync_with_lutris)
            actions.pack_start(self.sync_button, False, False, 0)

            if hasattr(service, "connect") and not service.is_connected():
                self.sync_switch.set_sensitive(False)
                self.sync_button.set_sensitive(False)

    def on_connect_clicked(self, button, service):
        if service.is_connected():
            service.disconnect()
            self._connect_button_toggle(False)

            self.sync_switch.set_sensitive(False)
            self.sync_button.set_sensitive(False)

            # Disable sync on disconnect
            if self.sync_switch and self.sync_switch.get_active():
                self.sync_switch.set_state(False)
        else:
            service.connect()
            self._connect_button_toggle(True)
            self.sync_switch.set_sensitive(True)
            self.sync_button.set_sensitive(True)

    def _connect_button_toggle(self, is_connected):
        self.connect_button.set_label("Disconnect" if is_connected else "Connect")

    def on_sync_button_clicked(self, button, sync_method):
        AsyncCall(sync_method, callback=self.on_service_synced)

    def on_service_synced(self, caller, data):
        parent = self.get_toplevel()
        if not isinstance(parent, Gtk.Window):
            # The sync dialog may have closed
            parent = Gio.Application.get_default().props.active_window
        NoticeDialog("Games synced", parent=parent)

    def on_switch_changed(self, switch, data):
        state = switch.get_active()
        write_setting('sync_at_startup', state, self.identifier)


class SyncServiceDialog(Gtk.Dialog):

    def __init__(self, parent=None):
        super().__init__(title="Import local games", parent=parent, use_header_bar=1)
        self.connect("delete-event", lambda *x: self.destroy())
        self.set_border_width(10)
        self.set_size_request(512, 0)

        box_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.get_content_area().add(box_outer)

        description_label = Gtk.Label()
        description_label.set_markup("You can choose which local game sources will get synced each\n"
                                     "time Lutris starts, or launch an immediate import of games.")
        box_outer.pack_start(description_label, False, False, 5)

        separator = Gtk.Separator()
        box_outer.pack_start(separator, False, False, 0)

        for service in get_services():
            sync_row = ServiceSyncRow(service, self)
            box_outer.pack_start(sync_row, False, True, 0)
        box_outer.show_all()
