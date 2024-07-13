"""DXVK helper module"""

import os

from lutris.settings import RUNTIME_DIR
from lutris.util.graphics import vkquery
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.wine.dll_manager import DLLManager

REQUIRED_VULKAN_API_VERSION = vkquery.vk_make_version(1, 3, 0)


class DXVKManager(DLLManager):
    component = "DXVK"
    base_dir = os.path.join(RUNTIME_DIR, "dxvk")
    versions_path = os.path.join(base_dir, "dxvk_versions.json")
    managed_dlls = ("dxgi", "d3d11", "d3d10core", "d3d9", "d3d8")
    releases_url = "https://api.github.com/repos/lutris/dxvk/releases"

    def can_enable(self):
        if os.environ.get("LUTRIS_NO_VKQUERY"):
            return True
        return LINUX_SYSTEM.is_vulkan_supported()

    def is_recommended_version(self, version):
        # DXVK 2.x and later require Vulkan 1.3, so if that iss lacking
        # we default to 1.x.
        if os.environ.get("LUTRIS_NO_VKQUERY"):
            return True
        vulkan_api_version = vkquery.get_expected_api_version()
        if vulkan_api_version and vulkan_api_version < REQUIRED_VULKAN_API_VERSION:
            return version.startswith("v1.")
        return super().is_recommended_version(version)

    @staticmethod
    def is_managed_dll(dll_path):
        """Check if a given DLL path is provided by the component

        Very basic check to see if a dll contains the string "dxvk".
        """
        try:
            with open(dll_path, "rb") as file:
                prev_block_end = b""
                while True:
                    block = file.read(2 * 1024 * 1024)  # 2 MiB
                    if not block:
                        break
                    if b"dxvk" in prev_block_end + block[:4]:
                        return True
                    if b"dxvk" in block:
                        return True

                    prev_block_end = block[-4:]
        except OSError:
            pass
        return False
