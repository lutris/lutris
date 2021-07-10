import os

from lutris.settings import RUNTIME_DIR
from lutris.util.wine.dll_manager import DLLManager


class DXVKNVAPIManager(DLLManager):
    component = "DXVK-NVAPI"
    base_dir = os.path.join(RUNTIME_DIR, "dxvk-nvapi")
    versions_path = os.path.join(base_dir, "dxvk-nvapi_versions.json")
    managed_dlls = ("nvapi", "nvapi64", "nvml")
    releases_url = "https://api.github.com/repos/lutris/dxvk-nvapi/releases"
