import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio

from lutris.gui.widgets.utils import get_runner_icon
from lutris.gui.dialogs import NoticeDialog
from lutris.services import get_services
from lutris.settings import read_setting, write_setting
from lutris.util.jobs import AsyncCall


class ServiceSyncRow(Gtk.HBox):

    def __init__(self, service):
        super(ServiceSyncRow, self).__init__()
        self.set_spacing(20)

        self.identifier = service.__name__.split('.')[-1]
        name = service.NAME

        icon = get_runner_icon(self.identifier)
        self.pack_start(icon, False, False, 0)

        label = Gtk.Label(xalign=0)
        label.set_markup("<b>{}</b>".format(name))
        self.pack_start(label, True, True, 0)

        actions = Gtk.VBox()
        self.pack_start(actions, False, False, 0)

        sync_switch = Gtk.Switch()
        sync_switch.set_tooltip_text("Sync when Lutris starts")
        sync_switch.props.valign = Gtk.Align.CENTER
        sync_switch.connect('notify::active', self.on_switch_changed)
        if read_setting('sync_at_startup', self.identifier) == 'True':
            sync_switch.set_state(True)
        actions.pack_start(sync_switch, False, False, 0)

        sync_button = Gtk.Button("Sync")
        sync_button.set_tooltip_text("Sync now")
        sync_button.connect('clicked', self.on_sync_button_clicked, service.sync_with_lutris)
        actions.pack_start(sync_button, False, False, 0)

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
        Gtk.Dialog.__init__(self, title="Configure local game import", parent=parent)
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
            sync_row = ServiceSyncRow(service)
            box_outer.pack_start(sync_row, False, True, 0)
        box_outer.show_all()
