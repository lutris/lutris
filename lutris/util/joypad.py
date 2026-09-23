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
