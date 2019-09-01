"""Wine prefix management"""
import os
from lutris.util.wine.registry import WineRegistry
from lutris.util.log import logger
from lutris.util import joypad, system, i18n
from lutris.util.display import DISPLAY_MANAGER

DESKTOP_KEYS = ["Desktop", "My Music", "My Pictures", "My Videos", "Personal"]


class WinePrefixManager:
    """Class to allow modification of Wine prefixes without the use of Wine"""

    hkcu_prefix = "HKEY_CURRENT_USER"

    def __init__(self, path):
        if not path:
            logger.warning("No path specified for Wine prefix")
        self.path = path

    def setup_defaults(self):
        """Sets the defaults for newly created prefixes"""
        self.override_dll("winemenubuilder.exe", "")
        self.override_dll("steamwebhelper.exe", "")
        try:
            self.desktop_integration()
        except OSError as ex:
            logger.error("Failed to setup desktop integration, the prefix may not be valid.")
            logger.exception(ex)

    def get_registry_path(self, key):
        """Matches registry keys to a registry file

        Currently, only HKEY_CURRENT_USER keys are supported.
        """
        if key.startswith(self.hkcu_prefix):
            return os.path.join(self.path, "user.reg")
        raise ValueError("Unsupported key '{}'".format(key))

    def get_key_path(self, key):
        if key.startswith(self.hkcu_prefix):
            return key[len(self.hkcu_prefix) + 1:]
        raise ValueError(
            "The key {} is currently not supported by WinePrefixManager".format(key)
        )

    def get_registry_key(self,key,subkey):
        registry = WineRegistry(self.get_registry_path(key))
        return registry.query(self.get_key_path(key),subkey)

    def set_registry_key(self, key, subkey, value):
        registry = WineRegistry(self.get_registry_path(key))
        registry.set_value(self.get_key_path(key), subkey, value)
        registry.save()

    def clear_registry_key(self, key):
        registry = WineRegistry(self.get_registry_path(key))
        registry.clear_key(self.get_key_path(key))
        registry.save()

    def clear_registry_subkeys(self, key, subkeys):
        registry = WineRegistry(self.get_registry_path(key))
        registry.clear_subkeys(self.get_key_path(key), subkeys)
        registry.save()

    def override_dll(self, dll, mode):
        key = self.hkcu_prefix + "/Software/Wine/DllOverrides"
        if mode.startswith("dis"):
            mode = ""
        if mode not in ("builtin", "native", "builtin,native", "native,builtin", ""):
            logger.error("DLL override '%s' mode is not valid", mode)
            return
        self.set_registry_key(key, dll, mode)

    def desktop_integration(self, desktop_dir=None):
        """Overwrite desktop integration"""
        DESKTOP_FOLDERS = []

        user = os.getenv("USER")
        user_dir = os.path.join(self.path, "drive_c/users/", user)

        for key in DESKTOP_KEYS:
            folder = self.get_registry_key(self.hkcu_prefix+"/Software/Microsoft/Windows/CurrentVersion/Explorer/Shell Folders",key)
            DESKTOP_FOLDERS.append(folder[folder.rfind("\\\\")+2:]) 

        if not desktop_dir:
            desktop_dir = user_dir
        else:
            desktop_dir = os.path.expanduser(desktop_dir)

        if system.path_exists(user_dir):
            # Replace desktop integration symlinks
            for item in DESKTOP_FOLDERS:
                path = os.path.join(user_dir, item)
                old_path = path + ".winecfg"

                if os.path.islink(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    try:
                        os.rmdir(path)
                    # We can't delete nonempty dir, so we rename as wine do.
                    except OSError:
                        os.rename(path, old_path)

                if desktop_dir != user_dir:
                    src_path = os.path.join(desktop_dir, item)
                    os.makedirs(src_path, exist_ok=True)
                    os.symlink(src_path, path)
                else:
                    # We use first the renamed dir, otherwise we make it.
                    if os.path.isdir(old_path):
                        os.rename(old_path, path)
                    else:
                        os.makedirs(path, exist_ok=True)

            # Security: Remove other symlinks.
            for item in os.listdir(user_dir):
                if item not in DESKTOP_FOLDERS and os.path.islink(item):
                    path = os.path.join(user_dir, item)
                    os.unlink(path)
                    os.makedirs(path)

    def set_crash_dialogs(self, enabled):
        """Enable or diable Wine crash dialogs"""
        self.set_registry_key(
            self.hkcu_prefix + "/Software/Wine/WineDbg",
            "ShowCrashDialog",
            1 if enabled else 0,
        )

    def set_virtual_desktop(self, enabled):
        """Enable or disable wine virtual desktop.
        The Lutris virtual desktop is refered to as 'WineDesktop', in Wine the
        virtual desktop name is 'default'.
        """
        path = self.hkcu_prefix + "/Software/Wine/Explorer"
        if enabled:
            self.set_registry_key(path, "Desktop", "WineDesktop")
            default_resolution = "x".join(DISPLAY_MANAGER.get_current_resolution())
            logger.debug("Enabling wine virtual desktop with default resolution of %s",
                         default_resolution)
            self.set_registry_key(
                self.hkcu_prefix + "/Software/Wine/Explorer/Desktops",
                "WineDesktop",
                default_resolution
            )
        else:
            self.clear_registry_key(path)

    def set_desktop_size(self, desktop_size):
        """Sets the desktop size if one is given but do not reset the key if
        one isn't.
        """
        path = self.hkcu_prefix + "/Software/Wine/Explorer/Desktops"
        if desktop_size:
            self.set_registry_key(path, "WineDesktop", desktop_size)

    def use_xvid_mode(self, enabled):
        """Set this to "Y" to allow wine switch the resolution using XVidMode extension."""
        self.set_registry_key(
            self.hkcu_prefix + "/Software/Wine/X11 Driver",
            "UseXVidMode",
            "Y" if enabled else "N",
        )

    def configure_joypads(self):
        joypads = joypad.get_joypads()
        key = self.hkcu_prefix + "/Software/Wine/DirectInput/Joysticks"
        self.clear_registry_key(key)
        for device, joypad_name in joypads:
            if "event" in device:
                disabled_joypad = "{} (js)".format(joypad_name)
            else:
                disabled_joypad = "{} (event)".format(joypad_name)
            self.set_registry_key(key, disabled_joypad, "disabled")
