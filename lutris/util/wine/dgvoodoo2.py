import os

from lutris.settings import RUNTIME_DIR
from lutris.util.wine.dll_manager import DLLManager


class dgvoodoo2Manager(DLLManager):
    name = "dgvoodoo2"
    human_name = "dgvoodoo2"
    managed_dlls = (
        "d3dimm",
        "ddraw",
        "glide",
        "glide2x",
        "glide3x",
    )
    managed_appdata_files = ["dgVoodoo/dgVoodoo.conf"]
    releases_url = "https://api.github.com/repos/lutris/dgvoodoo2/releases"
    proton_compatible = True
