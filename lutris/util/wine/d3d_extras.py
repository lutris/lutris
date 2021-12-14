import os

from lutris.settings import RUNTIME_DIR
from lutris.util.wine.dll_manager import DLLManager


class D3DExtrasManager(DLLManager):
    component = "D3D Extras"
    base_dir = os.path.join(RUNTIME_DIR, "d3d_extras")
    versions_path = os.path.join(base_dir, "d3d_extras_versions.json")
    managed_dlls = ("d3dx10_33", "d3dx10_34", "d3dx10_35", "d3dx10_36", "d3dx10_37", "d3dx10_38",
                    "d3dx10_39", "d3dx10_40", "d3dx10_41", "d3dx10_42", "d3dx10_43", "d3dx10",
                    "d3dx11_42", "d3dx11_43", "d3dx9_24", "d3dx9_25", "d3dx9_26", "d3dx9_27",
                    "d3dx9_28", "d3dx9_29", "d3dx9_30", "d3dx9_31", "d3dx9_32", "d3dx9_33",
                    "d3dx9_34", "d3dx9_35", "d3dx9_36", "d3dx9_37", "d3dx9_38", "d3dx9_39",
                    "d3dx9_40", "d3dx9_41", "d3dx9_42", "d3dx9_43", "d3dcompiler_33",
                    "d3dcompiler_34", "d3dcompiler_35", "d3dcompiler_36", "d3dcompiler_37",
                    "d3dcompiler_38", "d3dcompiler_39", "d3dcompiler_40", "d3dcompiler_41",
                    "d3dcompiler_42", "d3dcompiler_43", "d3dcompiler_46", "d3dcompiler_47",)
    releases_url = "https://api.github.com/repos/lutris/d3d_extras/releases"
