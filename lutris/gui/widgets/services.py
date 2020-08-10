"""Widget to connect to third party services"""
from gettext import gettext as _

from gi.repository import Gtk, GObject

from lutris.gui.widgets.utils import get_icon, get_main_window
from lutris.util.jobs import AsyncCall


class ServiceSyncBox(Gtk.Box):
    """Display components to interact with a service"""

    COL_SELECTED = 0
    COL_APPID = 1
    COL_NAME = 2
    COL_ICON = 3
    COL_DETAILS = 4
    MARGIN = 8

    __gsignals__ = {
        "service-connected": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        "service-disconnected": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        "service-refresh": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
    }

    def __init__(self, service):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_spacing(self.MARGIN)
        self.set_margin_top(self.MARGIN)
        self.set_margin_right(self.MARGIN)
        self.set_margin_left(self.MARGIN)
        self.set_margin_bottom(self.MARGIN)

        self.service = service
        self.identifier = service.__name__.split(".")[-1]
        self.is_connecting = False
        self.name = service.NAME

        service_logo = get_icon(self.service.ICON, size=(24, 24)) or Gtk.Label(self.name)
        service_logo.show()
        self.pack_start(service_logo, False, False, self.MARGIN)

        self.connect_button = Gtk.Button()
        self.connect_button.connect("clicked", self.on_connect_clicked)

        if service.ONLINE:
            self.refresh_button = Gtk.Button()
            self.refresh_button.connect("clicked", self.on_refresh_clicked)
            self.refresh_button.set_tooltip_text(_("Reload"))
            self.refresh_button.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU))
            self.pack_end(self.refresh_button, False, False, 0)
            self.pack_end(self.connect_button, False, False, 0)

        self.show_all()
        if self.service.ONLINE:
            AsyncCall(self._connect_button_toggle, None)

    def get_content_widget(self):
        center_alignment = Gtk.Alignment()
        center_alignment.set(0.5, 0.5, 0.1, 0.1)
        if self.service.ONLINE and not self.is_connecting:
            service_label = Gtk.Label(_("Connect to %s to import your library.") % self.name)
            service_label.set_justify(Gtk.Justification.CENTER)

            service_button = Gtk.Button(_("Connect your account"))
            service_button.connect("clicked", self.on_connect_clicked)

            service_box = Gtk.HBox()
            service_box.add(service_label)
            service_box.add(service_button)
            center_alignment.add(service_box)
        else:
            spinner = Gtk.Spinner()
            spinner.start()
            center_alignment.add(spinner)
        center_alignment.show_all()
        return center_alignment

    def on_refresh_clicked(self, _button):
        self.emit("service-refresh", self.identifier)

    def on_connect_clicked(self, _button):
        if self.service.is_connected():
            # Disable sync on disconnect
            self.emit("service-disconnected", self.identifier)
            self._connect_button_toggle()
            self.service.disconnect()
        else:
            self.emit("service-connected", self.identifier)
            self._connect_button_toggle()
            self.service.connect()
        return False

    def _connect_button_toggle(self):
        self.is_connecting = False
        if self.service.is_connected():
            icon_name = "system-log-out-symbolic"
            label = _("Disconnect")
            self.refresh_button.show()
        else:
            icon_name = "avatar-default-symbolic"
            label = _("Connect")
            self.refresh_button.hide()
        self.connect_button.set_tooltip_text(label)
        self.connect_button.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU))

    def load_games(self, force_reload=False):
        """Load the list of games in a treeview"""
        if self.service.ONLINE and not self.service.is_connected():
            return
        if force_reload:
            self.service.SERVICE.wipe_game_cache()

        self.is_connecting = True
        syncer = self.service.SYNCER()
        AsyncCall(syncer.load, None)

    def swap_content(self, old_widget, widget):
        widget_position = self.child_get_property(old_widget, 'position')
        old_widget.destroy()
        old_widget = widget
        self.pack_start(widget, True, True, 0)
        self.reorder_child(widget, widget_position)
