from lutris.util.nvidia import get_nvidia_dll_path
from lutris.util.wine.dll_manager import DLLManager


class DLSSManager(DLLManager):
    component = "DLSS"
    base_dir = get_nvidia_dll_path()
    managed_dlls = ("nvngx", )
    versions_path = None
    releases_url = None
