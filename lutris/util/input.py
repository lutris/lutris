import os


def check_joysticks():
    """Return list of connected joysticks."""
    number_joysticks = 0
    joysticks = []
    for device_number in range(0, 8):
        device_name = "/dev/input/js%d" % device_number
        if os.path.exists(device_name):
            number_joysticks = number_joysticks + 1
            joysticks.append(device_name)
    return joysticks
