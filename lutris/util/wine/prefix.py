"""Wine prefix management"""

import os

from lutris.settings import get_lutris_directory_settings, set_lutris_directory_settings
from lutris.util import joypad, system
from lutris.util.display import DISPLAY_MANAGER
from lutris.util.log import logger
from lutris.util.wine.registry import WineRegistry
from lutris.util.xdgshortcuts import get_xdg_entry

DESKTOP_KEYS = [
    "Desktop",
    "Personal",
    "My Music",
    "My Videos",
    "My Pictures",
    "{374DE290-123F-4565-9164-39C4925E467B}",  # Downloads
    "Templates",
]
DEFAULT_DESKTOP_FOLDERS = ["Desktop", "Documents", "Music", "Videos", "Pictures", "Downloads"]
DESKTOP_XDG = ["DESKTOP", "DOCUMENTS", "MUSIC", "VIDEOS", "PICTURES", "DOWNLOADS"]
DEFAULT_DLL_OVERRIDES = {
    "winemenubuilder": "",
}


def is_prefix(path):
    """Return True if the path is prefix"""
    return os.path.isdir(os.path.join(path, "drive_c")) and os.path.exists(os.path.join(path, "user.reg"))


def find_prefix(path):
    """Given an executable path, try to find a Wine prefix associated with it."""
    dir_path = path
    if not dir_path:
        logger.info("No path given, unable to guess prefix location")
        return
    dir_path = os.path.expanduser(dir_path)
    while dir_path != "/" and dir_path:
        dir_path = os.path.dirname(dir_path)
        if is_prefix(dir_path):
            return dir_path
        for prefix_dir in ("prefix", "pfx"):
            prefix_path = os.path.join(dir_path, prefix_dir)
            if is_prefix(prefix_path):
                return prefix_path


class WinePrefixManager:
    """Class to allow modification of Wine prefixes without the use of Wine"""

    hkcu_prefix = "HKEY_CURRENT_USER"
    hklm_prefix = "HKEY_LOCAL_MACHINE"

    def __init__(self, path):
        if not path:
            logger.warning("No path specified for Wine prefix")
        # expanduser() just in case- it should already be expanded.
        self.path = os.path.expanduser(path)

    def get_user_dir(self, default_user=None):
        user = default_user or os.getenv("USER") or "lutrisuser"
        return os.path.join(self.path, "drive_c/users/", user)

    @property
    def user_dir(self):
        """Returns the directory that contains the current user's profile in the WINE prefix."""
        return self.get_user_dir()

    @property
    def appdata_dir(self):
        """Returns the app-data directory for the user; this depends on a registry key."""
        user_dir = self.get_user_dir()
        folder = self.get_registry_key(
            self.hkcu_prefix + "/Software/Microsoft/Windows/CurrentVersion/Explorer/Shell Folders",
            "AppData",
        )
        if folder is None:
            logger.warning("Get Registry Key function returned NoneType to variable folder.")
        else:
            # Don't try to resolve the Windows path we get- there's
            # just two options, the Vista-and later option and the
            # XP-and-earlier option.
            if folder.lower().endswith("\\application data"):
                return os.path.join(user_dir, "Application Data")  # Windows XP
        return os.path.join(user_dir, "AppData/Roaming")  # Vista

    def setup_defaults(self):
        """Sets the defaults for newly created prefixes"""
        for dll, value in DEFAULT_DLL_OVERRIDES.items():
            self.override_dll(dll, value)

    def create_user_symlinks(self):
        """Link together user profiles created by Wine and Proton"""
        wine_user_dir = self.get_user_dir()
        proton_user_dir = self.get_user_dir(default_user="steamuser")
        if system.path_exists(wine_user_dir) and not system.path_exists(proton_user_dir, check_symlinks=True):
            system.create_symlink(wine_user_dir, proton_user_dir)
        elif system.path_exists(proton_user_dir) and not system.path_exists(wine_user_dir, check_symlinks=True):
            system.create_symlink(proton_user_dir, wine_user_dir)

    def get_registry_path(self, key):
        """Matches registry keys to a registry file

        Currently, only HKEY_CURRENT_USER keys are supported.
        """
        if key.startswith(self.hkcu_prefix):
            return os.path.join(self.path, "user.reg")
        if key.startswith(self.hklm_prefix):
            return os.path.join(self.path, "system.reg")
        raise ValueError("Unsupported key '{}'".format(key))

    def get_key_path(self, key):
        for prefix in (self.hkcu_prefix, self.hklm_prefix):
            if key.startswith(prefix):
                return key[len(prefix) + 1 :]
        raise ValueError("The key {} is currently not supported by WinePrefixManager".format(key))

    def get_registry_key(self, key, subkey):
        registry = WineRegistry(self.get_registry_path(key))
        return registry.query(self.get_key_path(key), subkey)

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

    def get_desktop_folders(self):
        """Return the list of desktop folder names loaded from the Windows registry"""
        desktop_folders = []
        for key in DESKTOP_KEYS:
            folder = self.get_registry_key(
                self.hkcu_prefix + "/Software/Microsoft/Windows/CurrentVersion/Explorer/Shell Folders",
                key,
            )
            if not folder:
                logger.warning("Couldn't load shell folder name for %s", key)
                continue
            desktop_folders.append(folder[folder.rfind("\\") + 1 :])
        return desktop_folders or DEFAULT_DESKTOP_FOLDERS

    def install_desktop_integration(self):
        """Replace WINE's desktop folders with links to the corresponding
        folders in your home directory."""
        user_dir = self.user_dir
        home_dir = os.path.expanduser("~")
        current_dir = self._get_desktop_integration_assignment() or user_dir

        if system.path_exists(user_dir, check_symlinks=True) and current_dir != home_dir:
            desktop_folders = self.get_desktop_folders()
            for i, item in enumerate(desktop_folders):
                path = os.path.join(user_dir, item)
                safe_path = path + ".winecfg"

                self._remove_desktop_folder(path, safe_path)

                # if we want to create a symlink and one is already there, just
                # skip to the next item.  this also makes sure we don't
                # find a dir (isdir only looks at the target of the symlink).
                src_path = get_xdg_entry(DESKTOP_XDG[i])
                if not src_path:
                    logger.error("No XDG entry found for %s, launcher not created", DESKTOP_XDG[i])
                else:
                    system.create_symlink(src_path, path)

            self._set_desktop_integration_assignment(home_dir)

    def remove_desktop_integration(self):
        """Replace the desktop integration links with proper folders."""
        user_dir = self.user_dir
        current_dir = self._get_desktop_integration_assignment() or user_dir

        if system.path_exists(user_dir) and current_dir != user_dir:
            desktop_folders = self.get_desktop_folders()
            for item in desktop_folders:
                path = os.path.join(user_dir, item)
                safe_path = path + ".winecfg"

                # Disintegration means the desktop folders in WINE are
                # actual directories not links, and that's all we want.
                if not os.path.islink(path):
                    continue

                self._remove_desktop_folder(path, safe_path)

                # We prefer to restore the previously saved directory.
                if os.path.isdir(safe_path):
                    os.rename(safe_path, path)
                else:
                    os.makedirs(path, exist_ok=True)

            self._set_desktop_integration_assignment(user_dir)

    def _remove_desktop_folder(self, path, safe_path):
        """Removes the link or directory at 'path'; if it is a non-empty directory
        this will rename it to 'safe_path' instead of removing it entirely."""
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            try:
                os.rmdir(path)
            except OSError:
                # We can't delete nonempty dir, so we rename as wine do.
                os.rename(path, safe_path)

    def _get_desktop_integration_assignment(self):
        try:
            # If the old tracking file is found, we'll read it, unlink it, and
            # save the setting in the new form.
            obsolete_path = os.path.join(self.path, ".lutris_destkop_integration")
            if os.path.isfile(obsolete_path):
                with open(obsolete_path, "r", encoding="utf-8") as f:
                    desktop_dir = f.read()
                self._set_desktop_integration_assignment(desktop_dir)
                os.unlink(obsolete_path)
        except Exception as ex:
            logger.exception("Unable to read Lutris desktop integration setting: %s", ex)

        settings = get_lutris_directory_settings(self.path)
        return settings.get("desktop_integration_directory", "")

    def _set_desktop_integration_assignment(self, desktop_dir):
        set_lutris_directory_settings(self.path, {"desktop_integration_directory": desktop_dir or ""})

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
            logger.debug(
                "Enabling wine virtual desktop with default resolution of %s",
                default_resolution,
            )
            self.set_registry_key(
                self.hkcu_prefix + "/Software/Wine/Explorer/Desktops",
                "WineDesktop",
                default_resolution,
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

    def set_dpi(self, dpi):
        """Sets the DPI for WINE to use. None to remove the Lutris setting,
        and leave WINE in control."""

        # Convert the old hidden file into a 'lutris.json' settings file
        obsolete_path = os.path.join(self.path, ".lutris_dpi_assignment")
        try:
            if os.path.isfile(obsolete_path):
                with open(obsolete_path, "r", encoding="utf-8") as f:
                    dpi_assigned = int(f.read())
                set_lutris_directory_settings(self.path, int(dpi_assigned))
                os.unlink(obsolete_path)
        except Exception as ex:
            logger.exception("Unable to read Lutris assigned DPI: %s", ex)

        settings = get_lutris_directory_settings(self.path)

        key_paths = [self.hkcu_prefix + "/Software/Wine/Fonts", self.hkcu_prefix + "/Control Panel/Desktop"]

        def assign_dpi(dpi):
            for key_path in key_paths:
                self.set_registry_key(key_path, "LogPixels", dpi)

        def is_lutris_dpi_assigned():
            """Check if Lutris assigned the DPI presently found in the registry."""
            try:
                dpi_assigned = settings.get("dpi_assigned")
                if dpi_assigned:
                    dpi_assigned = int(dpi_assigned)
                else:
                    return False
            except Exception as ex:
                logger.exception("Unable to read Lutris assigned DPI: %s", ex)
                return False

            for key_path in key_paths:
                if dpi_assigned != self.get_registry_key(key_path, "LogPixels"):
                    return False
            return True

        if dpi:
            assign_dpi(dpi)
            set_lutris_directory_settings(self.path, {"dpi_assigned": dpi})
        elif settings.get("dpi_assigned"):
            if is_lutris_dpi_assigned():
                assign_dpi(96)  # reset previous DPI
            set_lutris_directory_settings(self.path, {"dpi_assigned": ""})

    def configure_joypads(self):
        """Disables some joypad devices"""
        key = self.hkcu_prefix + "/Software/Wine/DirectInput/Joysticks"
        self.clear_registry_key(key)
        for _device, joypad_name in joypad.get_joypads():
            # Attempt at disabling mice that register as joysticks.
            # Although, those devices aren't returned by `get_joypads`
            # A better way would be to read /dev/input files directly.
            if "HARPOON RGB" in joypad_name:
                self.set_registry_key(key, "{} (js)".format(joypad_name), "disabled")
                self.set_registry_key(key, "{} (event)".format(joypad_name), "disabled")

        # This part of the code below avoids having 2 joystick interfaces
        # showing up simulatenously. It is not sure if it's still needed
        # so it is disabled for now. Street Fighter IV now runs in Proton
        # without this sort of hack.
        #
        # for device, joypad_name in joypads:
        #     if "event" in device:
        #         disabled_joypad = "{} (js)".format(joypad_name)
        #     else:
        #         disabled_joypad = "{} (event)".format(joypad_name)
        #     self.set_registry_key(key, disabled_joypad, "disabled")
