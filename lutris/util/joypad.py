try:
    import evdev
except ImportError:
    evdev = None


def get_joypads():
    """Return a list of tuples with the device and the joypad name"""
    if not evdev:
        return []
    device_names = evdev.list_devices()
    return [(dev, evdev.InputDevice(dev).name) for dev in device_names]
