"""Widget to connect to third party services"""
from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.widgets.utils import get_icon
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class ServiceSyncBox(Gtk.Box):
    """Display components to interact with a service"""

    COL_SELECTED = 0
    COL_APPID = 1
    COL_NAME = 2
    COL_ICON = 3
    COL_DETAILS = 4
    MARGIN = 8

    def __init__(self, service):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_spacing(self.MARGIN)
        self.set_margin_top(self.MARGIN)
        self.set_margin_right(self.MARGIN)
        self.set_margin_left(self.MARGIN)
        self.set_margin_bottom(self.MARGIN)

        self.service = service
        self.identifier = service.id
        self.name = service.name

        service_logo = get_icon(self.service.icon, size=(24, 24)) or Gtk.Label(self.name)
        service_logo.show()
        self.pack_start(service_logo, False, False, self.MARGIN)

        self.connect_button = Gtk.Button()
        self.connect_button.connect("clicked", self.on_connect_clicked)
        if self.service.online:
            self.pack_end(self.connect_button, False, False, 0)

        self.refresh_button = Gtk.Button()
        self.refresh_button.connect("clicked", self.on_refresh_clicked)
        self.refresh_button.set_tooltip_text(_("Reload"))
        self.refresh_button.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU))
        self.pack_end(self.refresh_button, False, False, 0)

        self.show_all()
        if self.service.online:
            AsyncCall(self._connect_button_toggle, None)

    def on_refresh_clicked(self, _button):
        logger.debug("Refreshing game list")
        self.service.wipe_game_cache()
        self.service.load()
        self.service.emit("service-games-loaded", self.service.id)

    def on_connect_clicked(self, _button):
        if self.service.is_connected():
            logger.debug("Disconnecting from %s", self.identifier)
            self._connect_button_toggle()
            self.service.logout()
        else:
            logger.debug("Connecting to %s", self.identifier)
            self._connect_button_toggle()
            self.service.login()
        return False

    def _connect_button_toggle(self):
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
