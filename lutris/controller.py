import threading
import time
from gi.repository import GLib
from lutris.util.joypad import get_devices
from lutris.util.log import logger

# same as joypad.py 
try:
    import evdev
except ImportError:
    evdev = None
except AttributeError as err:
    # 'evdev' versions 1.5 and earlier are incompatible with Python 3.11
    # and produce this exception; we won't be able to use these.
    logger.exception("python3-evdev failed to load, and won't be available: %s", err)
    evdev = None


ACTION_MAP = {
    304: "a", 305: "b", 307: "y", 308: "x",
    310: "left_bumper", 311: "right_bumper",
    544: "up", 545: "down", 546: "left", 547: "right",
}


HAT_MAP = {
    (17, -1): "up", (17, 1): "down",
    (16, -1): "left", (16, 1): "right",
}

TRIGGER_MAP = {
    2: "left_trigger", 5: "right_trigger",
}

class ControllerListener(threading.Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self._running = True
        self._trigger_states: dict[int, int] = {}

    def _find_device(self):
        devices = [d for d in get_devices()
                   if d.name.lower().find("pad") >= 0
                   or d.name.lower().find("controller") >= 0
                   or d.name.lower().find("joystick") >= 0]
        if not devices:
            devices = get_devices()
        return devices[0] if devices else None

    def run(self):
        while self._running:
            try:
                device = self._find_device()

                # If no device is found, wait and retry. 
                # This can happen if the controller is unplugged or not yet connected.
                if not device:
                    logger.debug("ControllerListener: no device found, retrying in 3s")
                    time.sleep(3)
                    continue

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
                        elif event.code in TRIGGER_MAP and self._trigger_states.get(event.code, 0) == 0:
                            self._trigger_states[event.code] = event.value
                            GLib.idle_add(self.callback, TRIGGER_MAP[event.code])
                        elif event.code in TRIGGER_MAP:
                            self._trigger_states[event.code] = event.value
                    if event.type == evdev.ecodes.EV_ABS and event.value == 0 and event.code in TRIGGER_MAP:
                        self._trigger_states[event.code] = 0

            except OSError:
                logger.debug("ControllerListener: device disconnected, retrying in 3s")
                time.sleep(3)
    
    def stop(self):
        self._running = False
