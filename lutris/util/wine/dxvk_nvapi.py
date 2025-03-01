import os

from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.nvidia import get_nvidia_dll_path
from lutris.util.wine.dll_manager import DLLManager


class DXVKNVAPIManager(DLLManager):
    name = "dxvk-nvapi"
    human_name = "DXVK-NVAPI"
    # apparently, nvofapi.dll (the 32 bit version) is not being included here -
    # see https://github.com/jp7677/dxvk-nvapi/pull/213
    managed_dlls = ("nvapi", "nvapi64", "nvml", "nvofapi64", "nvoptix", "nvencodeapi", "nvencodeapi64", "nvcuvid", "nvcuda")
    releases_url = "https://api.github.com/repos/lutris/dxvk-nvapi/releases"
    dlss_dlls = ("nvngx", "_nvngx", "nvngx_dlssg")

    def can_enable(self):
        return LINUX_SYSTEM.is_vulkan_supported()

    def disable_dll(self, system_dir, _arch, dll):  # pylint: disable=unused-argument
        """Remove DLL from Wine prefix"""
        wine_dll_path = os.path.join(system_dir, "%s.dll" % dll)
        if system.path_exists(wine_dll_path):
            os.remove(wine_dll_path)

    def enable(self):
        """Enable Dlls for the current prefix"""
        super().enable()
        dlss_dll_dir = get_nvidia_dll_path()
        if not dlss_dll_dir:
            return

        windows_path = os.path.join(self.prefix, "drive_c/windows")
        system_dir = os.path.join(windows_path, "system32")
        for dll in self.dlss_dlls:
            dll_path = os.path.join(dlss_dll_dir, "%s.dll" % dll)
            self.enable_dll(system_dir, "x64", dll_path)

    def disable(self):
        """Disable DLLs for the current prefix"""
        super().disable()
        windows_path = os.path.join(self.prefix, "drive_c/windows")
        system_dir = os.path.join(windows_path, "system32")
        for dll in self.dlss_dlls:
            self.disable_dll(system_dir, "x64", dll)
