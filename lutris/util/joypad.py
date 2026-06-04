# Standard Library
import binascii
import struct

# Lutris Modules
from lutris.util.gamecontrollerdb import GameControllerDB
from lutris.util.log import logger

# For Controller Listener
import threading
from gi.repository import GLib

try:
    import evdev
except ImportError:
    evdev = None
except AttributeError as err:
    # 'evdev' versions 1.5 and earlier are incompatible with Python 3.11
    # and produce this exception; we won't be able to use these.
    logger.exception("python3-evdev failed to load, and won't be available: %s", err)
    evdev = None


def get_devices():
    if not evdev:
        logger.warning("python3-evdev not installed, controller support not available")
        return []
    _devices = []
    for dev in evdev.list_devices():
        try:
            _devices.append(evdev.InputDevice(dev))
        except RuntimeError:
            pass
    return _devices


def get_joypads():
    """Return a list of tuples with the device and the joypad name"""
    return [(dev.path, dev.name) for dev in get_devices()]


def read_button(device):
    """Reference function for reading controller buttons and axis values.
    Not to be used as is.
    """
    # pylint: disable=no-member
    for event in device.read_loop():
        if event.type == evdev.ecodes.EV_KEY and event.value == 0:
            print("button %s (%s): %s" % (event.code, hex(event.code), event.value))
        if event.type == evdev.ecodes.EV_ABS:
            sticks = (0, 1, 3, 4)
            if event.code not in sticks or abs(event.value) > 5000:
                print("axis %s (%s): %s" % (event.code, hex(event.code), event.value))


def get_sdl_identifier(device_info):
    device_identifier = struct.pack(
        "<LLLL",
        device_info.bustype,
        device_info.vendor,
        device_info.product,
        device_info.version,
    )
    return binascii.hexlify(device_identifier).decode()


def get_controller_mappings():
    devices = get_devices()
    controller_db = GameControllerDB()

    controllers = []

    for device in devices:
        guid = get_sdl_identifier(device.info)
        if guid in controller_db.controllers:
            controllers.append((device, controller_db[guid]))

    return controllers

ACTION_MAP = {
    304: "a", 305: "b", 307: "y", 308: "x",
    544: "up", 545: "down", 546: "left", 547: "right",
}

HAT_MAP = {
    (17, -1): "up", (17, 1): "down",
    (16, -1): "left", (16, 1): "right",
}


class ControllerListener(threading.Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self._running = True

    def run(self):
        try:
            devices = [d for d in get_devices()
                       if d.name.lower().find("pad") >= 0
                       or d.name.lower().find("controller") >= 0
                       or d.name.lower().find("joystick") >= 0]
            if not devices:
                devices = get_devices()
                if not devices:
                    logger.debug("ControllerListener: no input devices found")
                    return

            device = devices[0]
            logger.debug("ControllerListener: listening on %s", device.name)

            for event in device.read_loop():
                if not self._running:
                    break

                if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                    action = ACTION_MAP.get(event.code)
                    if action:
                        GLib.idle_add(self.callback, action)

                if event.type == evdev.ecodes.EV_ABS and event.value != 0:
                    action = HAT_MAP.get((event.code, event.value))
                    if action:
                        GLib.idle_add(self.callback, action)

        except Exception as ex:
            logger.error("ControllerListener error: %s", ex)

    def stop(self):
        self._running = False
