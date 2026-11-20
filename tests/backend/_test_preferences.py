"""Preferences: game sources, storage paths, the Steam account and system info."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from lutris import settings
from lutris.backend import preferences
from lutris.exceptions import LutrisError
from lutris.util.test_config import setup_test_environment
from lutris.util.yaml import read_yaml_from_file

setup_test_environment()


@pytest.fixture
def saved(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str]:
    values: dict[tuple[str, str], str] = {}

    def read_setting(key: str, default: str = "", section: str = "lutris") -> str:
        return values.get((section, key), default)

    def read_bool_setting(key: str, default: bool = False, section: str = "lutris") -> bool:
        value = values.get((section, key))
        return default if value is None else value == "True"

    def write_setting(key: str, value: Any, section: str = "lutris") -> None:
        values[(section, key)] = str(value)

    monkeypatch.setattr(settings, "read_setting", read_setting)
    monkeypatch.setattr(settings, "read_bool_setting", read_bool_setting)
    monkeypatch.setattr(settings, "write_setting", write_setting)
    return values


def test_sources_can_be_turned_on_and_hidden_from_the_games_view(saved: dict[tuple[str, str], str]) -> None:
    async def run() -> None:
        sources = await preferences.list_sources()
        gog = next(source for source in sources if source.id == "gog")
        assert not gog.enabled and gog.in_games_view and gog.name == "GOG"

        await preferences.set_source_in_games_view("gog", False)
        await preferences.set_source_enabled("gog", True)
        gog = next(source for source in await preferences.list_sources() if source.id == "gog")
        # Turning a source on or off shows its games in the Games view again
        assert gog.enabled and gog.in_games_view

        await preferences.set_source_in_games_view("gog", False)
        assert not next(source for source in await preferences.list_sources() if source.id == "gog").in_games_view
        with pytest.raises(LutrisError):
            await preferences.set_source_enabled("no-such-store", True)

    asyncio.run(run())


def test_storage_paths_are_saved_where_lutris_reads_them(
    saved: dict[tuple[str, str], str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    scanned: list[str] = []
    monkeypatch.setattr(preferences, "scan_firmware_directory", scanned.append)
    bios = tmp_path / "bios"
    bios.mkdir()
    (bios / "scph1001.bin").write_bytes(b"bios")

    async def run() -> None:
        paths = await preferences.set_game_path(" /games ")
        assert paths.game_path == "/games"
        paths = await preferences.set_installer_cache_path(str(tmp_path / "missing" / "cache"))
        assert not paths.installer_cache_valid and paths.installer_cache_message
        paths = await preferences.set_installer_cache_path(str(tmp_path / "cache"))
        assert paths.installer_cache_valid and paths.installer_cache_path == str(tmp_path / "cache")
        paths = await preferences.set_bios_path(str(bios))
        assert paths.bios_path == str(bios) and paths.bios_warning == ""
        paths = await preferences.set_game_path("")
        assert paths.game_path.endswith("Games")

    asyncio.run(run())
    assert read_yaml_from_file(str(tmp_path / "system.yml"))["system"] == {"bios_path": str(bios)}
    assert saved[("lutris", "pga_cache_path")] == str(tmp_path / "cache")
    assert scanned == [str(bios)]


def test_bios_folders_that_scan_slowly_are_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preferences, "MAX_BIOS_FILES_IN_FOLDER", 2)
    for name in ("a.bin", "b.bin", "c.bin"):
        (tmp_path / name).write_bytes(b"bios")
    assert "many files" in preferences._bios_warning(str(tmp_path))
    assert preferences._bios_warning("") == ""


def test_steam_accounts_and_system_info(saved: dict[tuple[str, str], str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preferences,
        "get_steam_users",
        lambda: [{"steamid64": "1", "PersonaName": "Main"}, {"steamid64": "2"}],
    )

    async def run() -> None:
        await preferences.set_steam_account("2")
        accounts = await preferences.list_steam_accounts()
        assert [(account.name, account.active) for account in accounts] == [("Main", False), ("#2", True)]
        sections = await preferences.get_system_info()
        assert sections[0].title == "Features" and ("In Flatpak", "NO") in sections[0].items
        assert preferences.system_info_text(sections).startswith("[Features]\nVulkan support: ")

    asyncio.run(run())
