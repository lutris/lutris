import os
from lutris.util.wineregistry import WineRegistry
from lutris.util.log import logger
from lutris.util import joypad


class WinePrefixManager:
    """Class to allow modification of Wine prefixes without the use of Wine"""
    hkcu_prefix = "HKEY_CURRENT_USER"

    def __init__(self, path):
        self.path = path

    def setup_defaults(self):
        self.sandbox()
        self.override_dll("winemenubuilder.exe", "")

    def get_registry_path(self, key):
        if key.startswith(self.hkcu_prefix):
            return os.path.join(self.path, 'user.reg')
        else:
            raise ValueError("Unsupported key '{}'".format(key))

    def get_key_path(self, key):
        if key.startswith(self.hkcu_prefix):
            return key[len(self.hkcu_prefix) + 1:]
        else:
            raise ValueError(
                "The key {} is currently not supported by WinePrefixManager".format(key)
            )

    def set_registry_key(self, key, subkey, value):
        registry = WineRegistry(self.get_registry_path(key))
        registry.set_value(self.get_key_path(key), subkey, value)
        registry.save()

    def clear_registry_key(self, key):
        registry = WineRegistry(self.get_registry_path(key))
        registry.clear_key(self.get_key_path(key))
        registry.save()

    def override_dll(self, dll, mode):
        key = self.hkcu_prefix + "/Software/Wine/DllOverrides"
        if mode == "disabled":
            mode = ""
        if mode not in ("builtin", "native", "builtin,native", "native,builtin", ""):
            logger.error("DLL override '%s' mode is not valid", mode)
            return
        self.set_registry_key(key, dll, mode)

    def sandbox(self):
        user = os.getenv('USER')
        user_dir = os.path.join(self.path, "drive_c/users/", user)
        # Replace symlinks
        if os.path.exists(user_dir):
            for item in os.listdir(user_dir):
                path = os.path.join(user_dir, item)
                if os.path.islink(path):
                    os.unlink(path)
                    os.makedirs(path)

    def set_crash_dialogs(self, enabled):
        """Enable or diable Wine crash dialogs"""
        key = self.hkcu_prefix + "/Software/Wine/WineDbg"
        value = 1 if enabled else 0
        self.set_registry_key(key, "ShowCrashDialog", value)

    def configure_joypads(self):
        joypads = joypad.get_joypads()
        key = self.hkcu_prefix + '/Software/Wine/DirectInput/Joysticks'
        self.clear_registry_key(key)
        for device, joypad_name in joypads:
            if 'event' in device:
                disabled_joypad = "{} (js)".format(joypad_name)
            else:
                disabled_joypad = "{} (event)".format(joypad_name)
            self.set_registry_key(key, disabled_joypad, 'disabled')
