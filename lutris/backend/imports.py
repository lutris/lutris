"""Register games already present on disk without taking ownership of their files."""

import asyncio
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path

from lutris import settings
from lutris.config import write_game_config
from lutris.database.games import add_game
from lutris.exceptions import LutrisError
from lutris.game import GAME_INSTALLED, GAME_UPDATED, Game
from lutris.scanners import playtron
from lutris.scanners.default_installers import DEFAULT_INSTALLERS
from lutris.scanners.tosec import clean_rom_name, guess_platform, search_tosec_by_md5
from lutris.util.log import logger
from lutris.util.path_cache import add_to_path_cache, get_path_cache
from lutris.util.strings import slugify
from lutris.util.system import get_md5_hash, get_md5_in_zip


@dataclass(frozen=True)
class RomImportResult:
    name: str
    imported: bool
    error: str = ""


async def list_rom_files(folder: str) -> tuple[str, ...]:
    root = Path(folder)
    if not folder or not root.is_dir():
        raise LutrisError(_("Select a folder containing ROMs."))
    return await asyncio.to_thread(lambda: tuple(str(path) for path in sorted(root.rglob("*")) if path.is_file()))


async def import_rom(path: str) -> RomImportResult:
    try:
        game_id, name = await asyncio.to_thread(_register_rom, path)
    except (LutrisError, OSError, ValueError, zipfile.BadZipFile) as error:
        message = error.message if isinstance(error, LutrisError) else str(error)
        return RomImportResult(Path(path).name, False, message)
    if game_id:
        game = Game(game_id)
        add_to_path_cache(game)
        GAME_INSTALLED.fire(game)
        GAME_UPDATED.fire(game)
    return RomImportResult(name, bool(game_id))


def _register_rom(path: str) -> tuple[str | None, str]:
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise LutrisError(_("Select a ROM file."))
    for game_id, game_path in get_path_cache().items():
        if game_path == str(source):
            return None, Game(game_id).name

    checksum = get_md5_in_zip(str(source)) if source.suffix.lower() == ".zip" else get_md5_hash(str(source))
    for match in search_tosec_by_md5(checksum) or ():
        platform = guess_platform(match)
        if platform not in DEFAULT_INSTALLERS or not match.get("roms"):
            continue
        name = clean_rom_name(match["name"])
        config = deepcopy(DEFAULT_INSTALLERS[platform])
        options = config["game"]
        assert isinstance(options, dict)
        for key, value in options.items():
            if value == "rom":
                options[key] = str(source)
        slug = slugify(name)
        config_id = write_game_config(slug, config)
        try:
            game_id = add_game(
                name=name, runner=config["runner"], slug=slug, directory="", installed=1, configpath=config_id
            )
        except Exception:
            try:
                (Path(settings.CONFIG_DIR) / "games" / f"{config_id}.yml").unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not remove unused ROM configuration %s", config_id)
            raise
        return str(game_id), name
    raise LutrisError(_("No supported game matched this ROM's checksum."))


async def import_playtron_games() -> int:
    game_ids = await asyncio.to_thread(playtron.scan_all_libraries)
    for game_id in game_ids:
        game = Game(game_id)
        GAME_INSTALLED.fire(game)
        GAME_UPDATED.fire(game)
    return len(game_ids)
