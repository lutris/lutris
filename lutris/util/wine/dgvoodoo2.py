from pathlib import Path

from lutris.util.extract import ExtractError
from lutris.util.upstream import ReleaseSource
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
    release_source = ReleaseSource("dege-diosg/dgVoodoo2", r"^dgVoodoo[\d_]+\.zip$")
    proton_compatible = True

    def prepare_download(self, staged: Path) -> None:
        for target_arch, source_arch in (("x32", "x86"), ("x64", "x64")):
            target = staged / target_arch
            target.mkdir()
            for family in ("MS", "3Dfx"):
                for dll in (staged / family / source_arch).glob("*.dll"):
                    dll.rename(target / dll.name.lower())
        if not (staged / "x32" / "ddraw.dll").is_file():
            raise ExtractError("The dgVoodoo2 archive is missing its 32-bit DirectDraw DLL.")
