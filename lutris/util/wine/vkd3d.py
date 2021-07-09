import os

from lutris.settings import RUNTIME_DIR
from lutris.util.wine.dll_manager import DLLManager


class VKD3DManager(DLLManager):
    component = "VKD3D"
    base_dir = os.path.join(RUNTIME_DIR, "vkd3d")
    versions_path = os.path.join(base_dir, "vkd3d_versions.json")
    managed_dlls = ("d3d12", )
    releases_url = "https://api.github.com/repos/HansKristian-Work/vkd3d-proton/releases"
    archs = {
        32: 'x86',
        64: 'x64'
    }
