"""Export lutris games to Steam shortcuts"""

import binascii
import os
import re
import shlex
import shutil
from collections.abc import Iterable
from gettext import gettext as _
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, TypeAlias

from lutris.api import format_installer_url
from lutris.exceptions import LutrisError
from lutris.util import resources, system
from lutris.util.log import logger
from lutris.util.steam import vdf
from lutris.util.steam.config import convert_steamid64_to_steamid32, get_active_steamid64, get_user_data_dirs

if TYPE_CHECKING:
    from lutris.delegates import CommandLineUIDelegate
    from lutris.game import Game

SteamShortcut: TypeAlias = dict[str, Any]
_SCRIPT_DIRECTORY = "lutris-shortcuts"


def get_config_path() -> str:
    """Return config path for a Steam user"""
    userdatapath, user_ids = get_user_data_dirs()
    if not user_ids:
        return ""
    user_id = user_ids[0]
    if len(user_ids) > 1:
        active_account = get_active_steamid64()
        if active_account:
            active_account32 = convert_steamid64_to_steamid32(active_account)
            if active_account32 in user_ids:
                user_id = active_account32
    return os.path.join(userdatapath, user_id, "config")


def get_shortcuts_vdf_path() -> str:
    config_path = get_config_path()
    if not config_path:
        return ""
    return os.path.join(config_path, "shortcuts.vdf")


def vdf_file_exists() -> bool:
    try:
        return bool(get_shortcuts_vdf_path())
    except Exception as ex:
        logger.error("Failed to locate vdf file: %s", ex)
        return False


def matches_id(shortcut: SteamShortcut, game: "Game") -> bool:
    """Test if the game seems to be the one a shortcut refers to."""
    id_match = re.match(r".*lutris:rungameid/(\d+)", shortcut.get("LaunchOptions", ""))
    if not id_match:
        return False
    game_id = id_match.groups()[0]
    return game_id == game.id


def get_shortcuts() -> dict[str, SteamShortcut]:
    """Return all Steam shortcuts"""
    shortcut_path = get_shortcuts_vdf_path()
    return _read_shortcuts(Path(shortcut_path)) if shortcut_path else {}


def _read_shortcuts(shortcut_path: Path) -> dict[str, SteamShortcut]:
    try:
        payload = shortcut_path.read_bytes()
    except FileNotFoundError:
        return {}
    shortcuts: dict[str, SteamShortcut] = vdf.binary_loads(payload)["shortcuts"]
    return shortcuts


def _write_shortcuts(shortcut_path: Path, shortcuts: Iterable[SteamShortcut]) -> None:
    updated_shortcuts = {"shortcuts": {str(index): shortcut for index, shortcut in enumerate(shortcuts)}}
    with TemporaryDirectory(dir=shortcut_path.parent) as staging:
        staged_path = Path(staging) / shortcut_path.name
        staged_path.write_bytes(vdf.binary_dumps(updated_shortcuts))
        staged_path.replace(shortcut_path)


def _script_name(game: "Game") -> str:
    return f"lutris-{game.id}.sh"


def _legacy_script_path(game: "Game") -> Path:
    return Path.home() / ".local/share/applications" / f"lutris-{game.slug}.sh"


def _managed_script_path(game: "Game", shortcut_path: Path) -> Path:
    return shortcut_path.parent / _SCRIPT_DIRECTORY / _script_name(game)


def is_standalone_shortcut(shortcut: SteamShortcut, game: "Game") -> bool:
    """Recognize the script destinations used by Qt and legacy GTK shortcuts."""
    executable = Path(shortcut.get("Exe", "").strip('"'))
    return executable == _legacy_script_path(game) or (
        executable.name == _script_name(game) and executable.parent.name == _SCRIPT_DIRECTORY
    )


def get_game_shortcuts(game: "Game") -> list[SteamShortcut]:
    """List Steam entries that refer to this library game."""
    try:
        return [shortcut for shortcut in get_shortcuts().values() if matches_id(shortcut, game)]
    except Exception as ex:
        logger.error("Failed to read shortcut vdf file: %s", ex)
        return []


def shortcut_exists(game: "Game") -> bool:
    return bool(get_game_shortcuts(game))


def is_steam_game(game: "Game") -> bool:
    return game.runner_name == "steam"


def create_shortcut(game: "Game", launch_config_name: str | None = None, standalone: bool = False) -> None:
    if is_steam_game(game):
        logger.warning("Not updating shortcut for Steam game")
        return None
    logger.info("Creating Steam shortcut for %s", game)
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path:
        logger.warning("No Steam user configuration found, not creating a shortcut for %s", game)
        return None
    path = Path(shortcut_path)
    shortcut = (
        generate_standalone_shortcut(game, launch_config_name)
        if standalone
        else generate_shortcut(game, launch_config_name)
    )
    _write_shortcuts(path, [*_read_shortcuts(path).values(), shortcut])
    set_artwork(game)


def create_standalone_shortcut(game: "Game", launch_delegate: "CommandLineUIDelegate") -> None:
    """Export the selected launch configuration before registering its Steam entry."""
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path or is_steam_game(game):
        raise LutrisError(_("The selected shortcut destination is unavailable."))
    path = Path(shortcut_path)
    script = _managed_script_path(game, path)
    script.parent.mkdir(exist_ok=True)
    shortcut = generate_standalone_shortcut(game, launch_delegate.launch_config_name, script_path=script)
    with TemporaryDirectory(dir=script.parent) as staging:
        staged_script = Path(staging) / script.name
        game.write_script(str(staged_script), launch_delegate)
        if not staged_script.is_file() or not os.access(staged_script, os.X_OK):
            raise LutrisError(_("Could not generate the standalone launch script."))
        shortcuts = _read_shortcuts(path)
        staged_script.replace(script)
        try:
            _write_shortcuts(path, [*shortcuts.values(), shortcut])
        except OSError:
            script.unlink(missing_ok=True)
            raise
    try:
        set_artwork(game, appid=str(shortcut["appid"] + 0x100000000), config_path=str(path.parent))
    except OSError as error:
        logger.warning("Could not set Steam shortcut artwork for %s: %s", game, error)


def remove_shortcut(game: "Game", *, standalone: bool | None = None) -> None:
    logger.info("Removing Steam shortcut for %s", game)
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path:
        return
    path = Path(shortcut_path)
    remaining: list[SteamShortcut] = []
    removed: list[SteamShortcut] = []
    for shortcut in _read_shortcuts(path).values():
        if matches_id(shortcut, game) and (standalone is None or is_standalone_shortcut(shortcut, game) == standalone):
            removed.append(shortcut)
        else:
            remaining.append(shortcut)
    if not removed:
        return

    _write_shortcuts(path, remaining)
    script = _managed_script_path(game, path)
    executable = f'"{script}"'
    if any(shortcut.get("Exe") == executable for shortcut in removed) and not any(
        shortcut.get("Exe") == executable for shortcut in remaining
    ):
        try:
            script.unlink(missing_ok=True)
        except OSError as error:
            logger.warning("Could not remove Steam shortcut script %s: %s", script, error)


def _unsigned_appid(executable: str, name: str) -> int:
    return binascii.crc32((executable + name).encode("utf-8")) | 0x80000000


def generate_preliminary_id(game: "Game") -> int:
    lutris_binary = shutil.which("lutris")
    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "/usr/bin/flatpak"
    top = _unsigned_appid(f'"{lutris_binary}"', game.name)
    return (top << 32) | 0x02000000


def generate_appid(game: "Game") -> str:
    return str(generate_preliminary_id(game) >> 32)


def generate_shortcut_id(game: "Game") -> int:
    return (generate_preliminary_id(game) >> 32) - 0x100000000


def generate_shortcut(game: "Game", launch_config_name: str | None) -> SteamShortcut:
    lutris_binary = "lutris"

    launch_options = format_installer_url(
        {"action": "rungameid", "game_slug": game.id, "launch_config_name": launch_config_name}
    )

    launch_options = shlex.quote(launch_options)

    if is_flatpak_lutris():
        lutris_binary = "/usr/bin/flatpak"
        launch_options = "LC_ALL=C.UTF-8 %command% run net.lutris.Lutris " + launch_options
    return {
        "appid": generate_shortcut_id(game),
        "AppName": game.name,
        "Exe": f'"{lutris_binary}"',
        "StartDir": f'"{Path.home()}"',
        "icon": resources.get_icon_path(game.slug),
        "LaunchOptions": launch_options,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
    }


def generate_standalone_shortcut(
    game: "Game", launch_config_name: str | None, *, script_path: Path | None = None
) -> SteamShortcut:
    lutris_binary = shutil.which("lutris")

    launch_options = format_installer_url(
        {"action": "rungameid", "game_slug": game.id, "launch_config_name": launch_config_name}
    )

    launch_options = shlex.quote(launch_options)

    if lutris_binary == "/app/bin/lutris":
        launch_options = "run net.lutris.Lutris " + launch_options

    script = script_path or _legacy_script_path(game)
    executable = f'"{script}"'
    return {
        "appid": _unsigned_appid(executable, game.name) - 0x100000000 if script_path else generate_shortcut_id(game),
        "AppName": game.name,
        "Exe": executable,
        "StartDir": f'"{script.parent}/"',
        "icon": resources.get_icon_path(game.slug),
        "LaunchOptions": launch_options,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
    }


def is_flatpak_lutris() -> bool:
    return shutil.which("lutris") == "/app/bin/lutris"


def set_artwork(game: "Game", *, appid: str | None = None, config_path: str | None = None) -> None:
    config_path = config_path if config_path is not None else get_config_path()
    if not config_path:
        return None
    artwork_path = os.path.join(config_path, "grid")
    if not os.path.exists(artwork_path):
        os.makedirs(artwork_path)
    shortcut_id = appid if appid is not None else generate_appid(game)
    source_cover = resources.get_cover_path(game.slug)
    source_banner = resources.get_banner_path(game.slug)
    source_icon = resources.get_icon_path(game.slug)
    assets = [
        ("grid horizontal", source_banner, os.path.join(artwork_path, "{}.jpg".format(shortcut_id))),
        ("grid vertical", source_cover, os.path.join(artwork_path, "{}p.jpg".format(shortcut_id))),
        ("hero", source_banner, os.path.join(artwork_path, "{}_hero.jpg".format(shortcut_id))),
        ("icon", source_icon, os.path.join(artwork_path, "{}_icon.jpg".format(shortcut_id))),
    ]
    for name, source, target in assets:
        if not system.path_exists(target, exclude_empty=True):
            try:
                shutil.copyfile(source, target)
                logger.debug("Copied %s %s asset to %s", game, name, target)
            except FileNotFoundError as ex:
                logger.error("Failed to copy %s %s asset to %s: %s", game, name, target, ex)
