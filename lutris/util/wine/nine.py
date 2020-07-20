"""Gallium Nine helper module"""
# Standard Library
import os
import shutil

# Lutris Modules
from lutris.runners.commands.wine import wineexec
from lutris.util import system
from lutris.util.log import logger
from lutris.util.wine.cabinstall import CabInstaller


class NineUnavailable(RuntimeError):

    """Exception raised when Gallium Nine is not available"""


class NineManager:

    """Utility class to install and manage Gallium Nine to a Wine prefix"""

    nine_files = ("d3d9-nine.dll", "ninewinecfg.exe")
    mesa_files = ("d3dadapter9.so.1", )
    nine_dll = "d3d9"

    def __init__(self, path, prefix, arch):
        self.wine_path = path
        self.prefix = prefix
        self.wine_arch = arch

    @staticmethod
    def nine_is_supported():
        """Check if MESA is built with Gallium Nine state tracker support

        basic check for presence of d3dadapter9 library in 'd3d' subdirectory
        of system library directory
        """
        for mesa_file in NineManager.mesa_files:
            if not any(
                [os.path.exists(os.path.join(lib, "d3d", mesa_file)) for lib in system.LINUX_SYSTEM.iter_lib_folders()]
            ):
                return False

        return True

    @staticmethod
    def nine_is_installed():
        """Check if Gallium Nine standalone is installed on this system

        check 'wine/fakedlls' subdirectory of system library directory for Nine binaries
        """
        for nine_file in NineManager.nine_files:
            if not any(
                [
                    os.path.exists(os.path.join(lib, "wine/fakedlls", nine_file))
                    for lib in system.LINUX_SYSTEM.iter_lib_folders()
                ]
            ):
                return False

        return True

    @staticmethod
    def is_available():
        """Check if Gallium Nine can be enabled on this system"""
        return NineManager.nine_is_supported() and NineManager.nine_is_installed()

    def get_system_path(self, arch):
        """Return path of Windows system directory with binaries of chosen architecture"""
        windows_path = os.path.join(self.prefix, "drive_c/windows")

        if self.wine_arch == "win32" and arch == "x32":
            return os.path.join(windows_path, "system32")
        if self.wine_arch == "win64" and arch == "x32":
            return os.path.join(windows_path, "syswow64")
        if self.wine_arch == "win64" and arch == "x64":
            return os.path.join(windows_path, "system32")

        return None

    def is_prefix_prepared(self):
        if not all(
            system.path_exists(os.path.join(self.get_system_path("x32"), nine_file)) for nine_file in self.nine_files
        ):
            return False

        if self.wine_arch == "win64":
            if not all(
                system.path_exists(os.path.join(self.get_system_path("x64"), nine_file))
                for nine_file in self.nine_files
            ):
                return False

        return True

    def prepare_prefix(self):
        for nine_file in NineManager.nine_files:
            for lib in system.LINUX_SYSTEM.iter_lib_folders():
                nine_file_path = os.path.join(lib, "wine/fakedlls", nine_file)

                if (os.path.exists(nine_file_path) and CabInstaller.get_arch_from_dll(nine_file_path) == "win32"):
                    shutil.copy(nine_file_path, self.get_system_path("x32"))

                if self.wine_arch == "win64":
                    if (os.path.exists(nine_file_path) and CabInstaller.get_arch_from_dll(nine_file_path) == "win64"):
                        shutil.copy(nine_file_path, self.get_system_path("x64"))

            if not os.path.exists(os.path.join(self.get_system_path("x32"), nine_file)):
                raise NineUnavailable("could not install " + nine_file + " (x32)")

            if self.wine_arch == "win64":
                if not os.path.exists(os.path.join(self.get_system_path("x64"), nine_file)):
                    raise NineUnavailable("could not install " + nine_file + " (x64)")

    def move_dll(self, backup):
        """ Backup or restore dll used by Gallium Nine"""
        src_suff = "" if backup else ".orig"
        dst_suff = ".orig" if backup else ""

        wine_dll_path = os.path.join(self.get_system_path("x32"), NineManager.nine_dll + ".dll")
        if (
            os.path.exists(wine_dll_path + src_suff)
            and not os.path.islink(wine_dll_path + src_suff)
        ):
            shutil.move(wine_dll_path + src_suff, wine_dll_path + dst_suff)
            logger.debug("Moving file %s (x32)", wine_dll_path + src_suff)

        if self.wine_arch == "win64":
            wine_dll_path = os.path.join(self.get_system_path("x64"), NineManager.nine_dll + ".dll")
            if (
                os.path.exists(wine_dll_path + src_suff)
                and not os.path.islink(wine_dll_path + src_suff)
            ):
                shutil.move(wine_dll_path + src_suff, wine_dll_path + dst_suff)
                logger.debug("Moving file %s (x64)", wine_dll_path + src_suff)

    def enable(self):
        if not self.nine_is_supported():
            raise NineUnavailable("Nine is not supported on this system")
        if not self.nine_is_installed():
            raise NineUnavailable("Nine Standalone is not installed")
        if not self.is_prefix_prepared():
            self.prepare_prefix()

        self.move_dll(True)

        wineexec(
            "ninewinecfg",
            args="-e",
            wine_path=self.wine_path,
            prefix=self.prefix,
            blocking=True,
        )

    def disable(self):
        if self.is_prefix_prepared():
            # DXVK might to restore the dll - backup it again before calling ninewinecfg
            self.move_dll(True)

            wineexec(
                "ninewinecfg",
                args="-d",
                wine_path=self.wine_path,
                prefix=self.prefix,
                blocking=True,
            )

            self.move_dll(False)
