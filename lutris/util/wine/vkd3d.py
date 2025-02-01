from lutris.util.linux import LINUX_SYSTEM
from lutris.util.wine.dll_manager import DLLManager


class VKD3DManager(DLLManager):
    name = "vkd3d"
    human_name = "VKD3D"
    managed_dlls = ("d3d12", "d3d12core")
    releases_url = "https://api.github.com/repos/lutris/vkd3d/releases"

    def can_enable(self):
        return LINUX_SYSTEM.is_vulkan_supported()
