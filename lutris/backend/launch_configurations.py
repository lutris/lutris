"""Translate launch configuration choices into data a frontend can display."""

from dataclasses import dataclass
from gettext import gettext as _
from typing import TYPE_CHECKING

from lutris.backend.games import game_info_from
from lutris.backend.models import GameInfo
from lutris.delegates import LaunchUIDelegate
from lutris.exceptions import LutrisError
from lutris.game import Game

if TYPE_CHECKING:
    from lutris.config import LaunchConfigDict


@dataclass(frozen=True)
class LaunchChoice:
    index: int
    remember: bool


def configuration_names(configs: list["LaunchConfigDict"]) -> tuple[str, ...]:
    """Return the primary configuration label followed by the named alternatives."""
    return (_("Primary configuration"), *(str(config.get("name") or _("Unnamed configuration")) for config in configs))


def preferred_index(configs: list["LaunchConfigDict"], name: str | None, index: int | None) -> int | None:
    """Resolve a saved selection, keeping its index when duplicate names exist."""
    if index == 0 or name == Game.PRIMARY_LAUNCH_CONFIG_NAME:
        return 0
    if name:
        if isinstance(index, int) and 0 < index <= len(configs) and configs[index - 1].get("name") == name:
            return index
        return next((i for i, config in enumerate(configs, 1) if config.get("name") == name), None)
    return None


class BackendLaunchUIDelegate(LaunchUIDelegate):
    """Adapt the core's launch selection hook for frontends that consume plain data."""

    def __init__(self, *, choose_again: bool = False) -> None:
        self._choose_again = choose_again

    def choose_launch_configuration(
        self, game: GameInfo, names: tuple[str, ...], current_index: int | None
    ) -> LaunchChoice | None:
        """Ask the frontend to choose an index, or return None on cancellation."""
        raise NotImplementedError

    def select_game_launch_config(self, game: Game) -> "LaunchConfigDict | None":
        config = game.config
        if not config:
            return {}
        options = config.game_level.get("game", {})
        configs: list["LaunchConfigDict"] = options.get("launch_configs") or []
        if not configs:
            return {}
        index = preferred_index(
            configs, options.get("preferred_launch_config_name"), options.get("preferred_launch_config_index")
        )
        if index is None or self._choose_again:
            choice = self.choose_launch_configuration(game_info_from(game), configuration_names(configs), index)
            if choice is None:
                return None
            index = choice.index
            if not 0 <= index <= len(configs):
                raise LutrisError(_("Invalid launch configuration."))
            if choice.remember:
                options["preferred_launch_config_index"] = index
                options["preferred_launch_config_name"] = (
                    configs[index - 1].get("name") if index else Game.PRIMARY_LAUNCH_CONFIG_NAME
                )
            else:
                options.pop("preferred_launch_config_index", None)
                options.pop("preferred_launch_config_name", None)
            config.save()
        return configs[index - 1] if index else {}
