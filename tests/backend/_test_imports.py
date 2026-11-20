"""Import local ROMs without taking ownership of the source files."""

import asyncio
import hashlib
from pathlib import Path

import pytest

from lutris import settings
from lutris.backend import game_maintenance, imports
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.util import path_cache
from lutris.util.test_config import setup_test_environment

setup_test_environment()


def test_rom_import_deduplicates_resolved_paths_and_preserves_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(path_cache, "GAME_PATH_CACHE_PATH", str(tmp_path / "path-cache.json"))
    path_cache.get_path_cache.cache_clear()
    (tmp_path / "games").mkdir()
    rom = tmp_path / "example.sfc"
    rom.write_bytes(b"fixture")
    alternate = tmp_path / "alternate.sfc"
    alternate.symlink_to(rom)
    checksums: list[str] = []

    def match(checksum: str) -> list[dict[str, object]]:
        checksums.append(checksum)
        return [{"name": "Qt Import Test (USA)", "category": {"name": "Super Famicom"}, "roms": [{}]}]

    monkeypatch.setattr(imports, "search_tosec_by_md5", match)

    async def run() -> None:
        assert (await imports.import_rom(str(rom))).imported
        rows = games_db.get_games(filters={"slug": "qt-import-test"})
        assert len(rows) == 1
        game_id = rows[0]["id"]
        try:
            duplicate = await imports.import_rom(str(alternate))
            assert not duplicate.imported and not duplicate.error
            state = await game_maintenance.get_maintenance_info(game_id)
            assert state.installed and not state.directory and state.files_unavailable_reason
            with pytest.raises(LutrisError):
                await game_maintenance.uninstall_game(game_id, state, trash_files=True)
            await game_maintenance.uninstall_game(game_id, state, remove_from_library=True)
        finally:
            games_db.delete_game(game_id)
            path_cache.get_path_cache.cache_clear()

    asyncio.run(run())
    assert checksums == [hashlib.md5(b"fixture").hexdigest()]
    assert rom.read_bytes() == b"fixture" and alternate.is_symlink()
