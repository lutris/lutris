"""DXVK helper module"""
import os

from lutris.settings import RUNTIME_DIR
from lutris.util.wine.dll_manager import DLLManager


class UnavailableDXVKVersion(RuntimeError):
    """Exception raised when a version of DXVK is not found"""


class DXVKManager(DLLManager):
    component = "DXVK"
    base_dir = os.path.join(RUNTIME_DIR, "dxvk")
    versions_path = os.path.join(base_dir, "dxvk_versions.json")
    managed_dlls = ("dxgi", "d3d11", "d3d10core", "d3d9", "d3d12")
    releases_url = "https://api.github.com/repos/lutris/dxvk/releases"

    @staticmethod
    def is_managed_dll(dll_path):
        """Check if a given DLL path is provided by the component

        Very basic check to see if a dll contains the string "dxvk".
        """
        try:
            with open(dll_path, 'rb') as file:
                prev_block_end = b''
                while True:
                    block = file.read(2 * 1024 * 1024)  # 2 MiB
                    if not block:
                        break
                    if b'dxvk' in prev_block_end + block[:4]:
                        return True
                    if b'dxvk' in block:
                        return True

                    prev_block_end = block[-4:]
        except OSError:
            pass
        return False
