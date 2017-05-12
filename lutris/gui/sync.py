import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from lutris.gui.widgets import get_runner_icon


class ServiceSyncRow(Gtk.HBox):

    def __init__(self, service):
        super(ServiceSyncRow, self).__init__()
        self.set_spacing(20)

        identifier = service.__name__.split('.')[-1]
        name = service.NAME

        icon = get_runner_icon(identifier)
        self.pack_start(icon, False, False, 0)

        label = Gtk.Label(xalign=0)
        label.set_markup("<b>{}</b>".format(name))
        self.pack_start(label, True, True, 0)

        actions = Gtk.VBox()
        self.pack_start(actions, False, False, 0)

        sync_switch = Gtk.Switch()
        sync_switch.set_tooltip_text("Sync when Lutris starts")
        sync_switch.props.valign = Gtk.Align.CENTER
        actions.pack_start(sync_switch, False, False, 0)

        sync_button = Gtk.Button("Sync")
        sync_button.set_tooltip_text("Sync now")
        sync_button.connect('clicked', lambda w: GLib.idle_add(service.sync_with_lutris))
        actions.pack_start(sync_button, False, False, 0)


class SyncServiceWindow(Gtk.Window):

    def __init__(self, services):
        Gtk.Window.__init__(self, title="Import local games")
        self.set_border_width(10)
        self.set_size_request(512, 0)

        box_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(box_outer)

        description_label = Gtk.Label()
        description_label.set_markup("You can import games from local game sources, \n"
                                     "you can also choose to sync everytime Lutris starts")
        box_outer.pack_start(description_label, False, False, 5)

        separator = Gtk.Separator()
        box_outer.pack_start(separator, False, False, 0)

        for service in services:
            sync_row = ServiceSyncRow(service)
            box_outer.pack_start(sync_row, False, True, 0)
        box_outer.show_all()
