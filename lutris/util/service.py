import dbus
from gi.repository import Gtk, GObject
from lutris.gui.lutriswindow import LutrisWindow
from lutris.util.log import logger

DBUS_INTERFACE = 'net.lutris.main'


class LutrisService(dbus.service.Object):
    """Main D-Bus Lutris service."""
    def __init__(self, bus_name, object_path, name):
        dbus.service.Object.__init__(self, bus_name, object_path, name)
        self.running = False
        self.lutris_window = None

    def stop(self):
        """ stop the dbus controller and remove from the bus """
        self.remove_from_connection()

    @dbus.service.method(DBUS_INTERFACE, out_signature='b')
    def is_running(self):
        return self.running

    @dbus.service.method(DBUS_INTERFACE, in_signature='i')
    def run(self, timestamp):
        if self.is_running():
            self.lutris_window.window.present_with_time(timestamp)
        else:
            logger.info("Welcome to Lutris")
            self.running = True
            self.lutris_window = LutrisWindow(service=self)
            GObject.threads_init()
            Gtk.main()
            self.running = False

    @dbus.service.method(DBUS_INTERFACE, in_signature='s')
    def install_game(self, game_ref):
        self.lutris_window.on_install_clicked(game_ref=game_ref)

    @dbus.service.method(DBUS_INTERFACE, in_signature='i')
    def run_game(self, game_id):
        self.lutris_window.on_game_run(game_id=game_id)


def get_bus():
    return dbus.SessionBus()


def get_service(bus):
    request = bus.request_name(DBUS_INTERFACE, dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
    if request != dbus.bus.REQUEST_NAME_REPLY_EXISTS:
        service = LutrisService(bus, '/', DBUS_INTERFACE)
    else:
        proxy = bus.get_object(DBUS_INTERFACE, "/")
        service = dbus.Interface(proxy, DBUS_INTERFACE)
    return service
