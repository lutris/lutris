# Standard Library
import binascii
import struct

# Lutris Modules
from lutris.util.gamecontrollerdb import GameControllerDB
from lutris.util.log import logger

try:
    import evdev
except ImportError:
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
    return [(dev.fn, dev.name) for dev in get_devices()]


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
