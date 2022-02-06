import os

from lutris.settings import RUNTIME_DIR
from lutris.util.wine.dll_manager import DLLManager


class dgvoodoo2Manager(DLLManager):
    component = "dgvoodoo2"
    base_dir = os.path.join(RUNTIME_DIR, "dgvoodoo2")
    versions_path = os.path.join(base_dir, "dgvoodoo2_versions.json")
    managed_dlls = ("d3dimm", "ddraw", "glide", "glide2x", "glide3x", )
    managed_user_files = ("AppData/Roaming/dgVoodoo/dgVoodoo.conf", )
    releases_url = "https://api.github.com/repos/lutris/dgvoodoo2/releases"
