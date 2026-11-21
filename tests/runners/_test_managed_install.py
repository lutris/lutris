import io
import os
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from lutris import settings
from lutris.delegates import InstallUIDelegate
from lutris.runners.runner import Runner
from lutris.runners.xenia import xenia
from lutris.util.upstream import FileSource


def test_managed_install_keeps_appimages_inside_archives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    destination = tmp_path / "runner"

    def download(url: str, path: str) -> bool:
        with tarfile.open(path, "w:gz") as archive:
            for name in ("wrapper/runner", "wrapper/assets/Runner.AppImage"):
                data = b"fixture"
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return True

    delegate = InstallUIDelegate()
    delegate.download_install_file = download
    Runner().download_and_extract("https://example.invalid/runner.tar.gz", delegate, str(destination), "runner")
    assert os.access(destination / "runner", os.X_OK)
    assert (destination / "assets" / "Runner.AppImage").read_bytes() == b"fixture"
    assert not list((tmp_path / "cache").iterdir())


@pytest.mark.parametrize("filename", ["Runner-v2.appimage", "runner.zip"])
def test_managed_install_resolves_appimage_entry_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    destination = tmp_path / "runner"

    def download(url: str, path: str) -> bool:
        if filename.endswith(".zip"):
            with ZipFile(path, "w") as archive:
                archive.writestr("wrapper/Runner-v2.appimage", b"fixture")
        else:
            Path(path).write_bytes(b"fixture")
        return True

    delegate = InstallUIDelegate()
    delegate.download_install_file = download
    Runner().download_and_extract(f"https://example.invalid/{filename}", delegate, str(destination), "Runner.AppImage")

    executable = destination / "Runner.AppImage"
    assert executable.read_bytes() == b"fixture"
    assert os.access(executable, os.X_OK)
    assert not (destination / "Runner-v2.appimage").exists()


def test_xenia_installs_its_emulator_inside_its_runner_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RUNNER_DIR", str(tmp_path / "runners"))
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    runner = xenia()
    runner.upstream = FileSource("https://example.invalid/xenia.tar.gz")
    runner.upstream_arch = None

    def download(url: str, path: str) -> bool:
        with tarfile.open(path, "w:gz") as archive:
            data = b"fixture"
            info = tarfile.TarInfo("xenia_canary.exe")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        return True

    delegate = InstallUIDelegate()
    delegate.download_install_file = download

    assert not runner.is_installed()
    runner.install(delegate, version="ge-proton")
    assert runner.is_installed()
    assert Path(runner.game_exe) == tmp_path / "runners" / "xenia" / "xenia_canary.exe"
