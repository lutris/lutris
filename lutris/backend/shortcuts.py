"""Manage library game shortcuts without depending on a frontend."""

import asyncio
from dataclasses import dataclass
from gettext import gettext as _
from threading import Lock
from typing import TYPE_CHECKING, Literal

from lutris.backend.launch_configurations import configuration_names
from lutris.delegates import CommandLineUIDelegate
from lutris.exceptions import LutrisError
from lutris.game import Game
from lutris.util import xdgshortcuts
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.steam import shortcut as steam_shortcut

if TYPE_CHECKING:
    from lutris.config import LaunchConfigDict

type ShortcutKind = Literal["desktop", "menu", "steam", "steam_big_picture"]


@dataclass(frozen=True)
class ShortcutTarget:
    kind: ShortcutKind
    label: str
    exists: bool


@dataclass(frozen=True)
class GameShortcuts:
    targets: tuple[ShortcutTarget, ...]
    configuration_labels: tuple[str, ...]
    configuration_names: tuple[str, ...]


_lock = Lock()


def _installed_game(game_id: str) -> Game:
    game = Game(game_id)
    if not game.is_installed:
        raise LutrisError(_("This game must be installed to manage its shortcuts."))
    return game


def _get_shortcuts(game: Game) -> GameShortcuts:
    targets: list[ShortcutTarget] = []
    if xdgshortcuts.get_xdg_entry("DESKTOP"):
        targets.append(
            ShortcutTarget("desktop", _("Desktop"), xdgshortcuts.desktop_launcher_exists(game.slug, game.id))
        )
    targets.append(ShortcutTarget("menu", _("Application Menu"), xdgshortcuts.menu_launcher_exists(game.slug, game.id)))
    if not steam_shortcut.is_steam_game(game) and steam_shortcut.vdf_file_exists():
        standalone_kinds = {
            steam_shortcut.is_standalone_shortcut(shortcut, game)
            for shortcut in steam_shortcut.get_game_shortcuts(game)
        }
        targets.append(ShortcutTarget("steam", _("Steam"), False in standalone_kinds))
        if True in standalone_kinds or not LINUX_SYSTEM.is_flatpak():
            targets.append(
                ShortcutTarget("steam_big_picture", _("Steam Big Picture (Standalone)"), True in standalone_kinds)
            )
    config = game.config
    game_options = config.game_level.get("game", {}) if config else {}
    alternatives: list["LaunchConfigDict"] = game_options.get("launch_configs") or []
    named = [item for item in alternatives if item.get("name")]
    return GameShortcuts(tuple(targets), configuration_names(named), ("", *(str(item["name"]) for item in named)))


async def get_shortcuts(game_id: str) -> GameShortcuts:
    """List available destinations and any shortcuts already present."""
    return await asyncio.to_thread(_read_shortcuts, game_id)


def _read_shortcuts(game_id: str) -> GameShortcuts:
    with _lock:
        return _get_shortcuts(_installed_game(game_id))


async def set_shortcut(game_id: str, kind: str, present: bool, configuration: str = "") -> GameShortcuts:
    """Create or remove a shortcut, then return the current destinations."""
    return await asyncio.to_thread(_set_shortcut, game_id, kind, present, configuration)


def _set_shortcut(game_id: str, kind: str, present: bool, configuration: str) -> GameShortcuts:
    with _lock:
        game = _installed_game(game_id)
        current = _get_shortcuts(game)
        target = next((target for target in current.targets if target.kind == kind), None)
        if not target:
            raise LutrisError(_("The selected shortcut destination is unavailable."))
        if target.exists == present:
            return current
        if present and configuration not in current.configuration_names:
            raise LutrisError(_("The selected launch configuration is no longer available."))
        try:
            if target.kind in {"steam", "steam_big_picture"}:
                standalone = target.kind == "steam_big_picture"
                if present:
                    if standalone:
                        steam_shortcut.create_standalone_shortcut(game, CommandLineUIDelegate(configuration))
                    else:
                        steam_shortcut.create_shortcut(game, configuration)
                else:
                    steam_shortcut.remove_shortcut(game, standalone=standalone)
            elif present:
                xdgshortcuts.create_launcher(
                    game.slug, game.id, game.name, configuration, desktop=kind == "desktop", menu=kind == "menu"
                )
            else:
                xdgshortcuts.remove_launcher(game.slug, game.id, desktop=kind == "desktop", menu=kind == "menu")
        except OSError as error:
            raise LutrisError(_("Could not update the %s shortcut.") % target.label) from error
        return _get_shortcuts(game)
