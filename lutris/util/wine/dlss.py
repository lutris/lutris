from lutris.util.wine.dll_manager import DLLManager
from lutris.util.nvidia import get_nvidia_dll_path

class DLSSManager(DLLManager):
    component = "DLSS"
    base_dir = get_nvidia_dll_path()
    managed_dlls = ("nvngx", )
    versions_path = None
    releases_url = None
