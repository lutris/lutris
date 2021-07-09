from lutris.util.wine.dll_manager import DLLManager


class DLSSManager(DLLManager):
    component = "DLSS"
    base_dir = "/usr/lib/nvidia/wine"
    managed_dlls = ("nvngx", )
    versions_path = None
    releases_url = None
