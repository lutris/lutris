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


def read_button(device):
    """Reference function for reading controller buttons and axis values.
    Not to be used as is.
    """
    for event in device.read_loop():
        if event.type == evdev.ecodes.EV_KEY and event.value == 0:
            print "button %s (%s): %s" % (event.code, hex(event.code), event.value)
        if event.type == evdev.ecodes.EV_ABS:
            sticks = (0, 1, 3, 4)
            if event.code not in sticks or abs(event.value) > 5000:
                print "axis %s (%s): %s" % (event.code, hex(event.code), event.value)

    # Unreacheable return statement, to return the even, place a 'break' in the
    # for loop
    return event
