"""Runner loaders"""

from __future__ import annotations

__all__ = [
    "atari800",
    "azahar",
    "cemu",
    "dolphin",
    "dosbox",
    "duckstation",
    "easyrpg",
    "flatpak",
    "fsuae",
    "hatari",
    "jzintv",
    "libretro",
    "linux",
    "mame",
    "mednafen",
    "mupen64plus",
    "o2em",
    "osmose",
    "pcsx2",
    "pico8",
    "redream",
    "reicast",
    "rpcs3",
    "ryujinx",
    "scummvm",
    "shadps4",
    "snes9x",
    "steam",
    "vice",
    "vita3k",
    "web",
    "wine",
    "xemu",
    "xenia",
    "yuzu",
    "zdoom",
]

from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type, cast

from lutris.exceptions import LutrisError, MisconfigurationError

if TYPE_CHECKING:
    from lutris.runners.runner import Runner

ADDON_RUNNERS: Dict[str, Type[Runner]] = {}
_cached_runner_human_names = {}


class InvalidRunnerError(MisconfigurationError):
    """Raise if a runner name is used that is not known to Lutris."""


class RunnerInstallationError(LutrisError):
    """Raised if the attempt to install a runner fails, perhaps because
    of invalid data from a server."""


class NonInstallableRunnerError(LutrisError):
    """Raised if installed a runner that Lutris cannot install, like Flatpak.
    These must be installed separately."""


def get_runner_module(runner_name: str) -> ModuleType:
    if not is_valid_runner_name(runner_name):
        raise InvalidRunnerError("Invalid runner name '%s'" % runner_name)
    module = __import__("lutris.runners.%s" % runner_name, globals(), locals(), [runner_name], 0)
    if not module:
        raise InvalidRunnerError("Runner module for '%s' could not be imported." % runner_name)
    return module


def import_runner(runner_name: str) -> Type[Runner]:
    """Dynamically import a runner class."""
    if runner_name in ADDON_RUNNERS:
        return ADDON_RUNNERS[runner_name]

    runner_module = get_runner_module(runner_name)
    return cast(Type[Runner], getattr(runner_module, runner_name))


def import_task(runner: str, task: str) -> Callable[..., Any]:
    """Return a runner task."""
    runner_module = get_runner_module(runner)
    return cast(Callable[..., Any], getattr(runner_module, task))


def get_installed(sort: bool = True) -> List[Runner]:
    """Return a list of installed runners (class instances)."""
    installed = []
    for runner_name in __all__:
        runner = import_runner(runner_name)()
        if runner.is_installed():
            installed.append(runner)
    return sorted(installed) if sort else installed


def inject_runners(runners: Dict[str, Type[Runner]]) -> None:
    for runner_name in runners:
        if runner_name not in __all__:
            ADDON_RUNNERS[runner_name] = runners[runner_name]
            __all__.append(runner_name)
    _cached_runner_human_names.clear()


def get_runner_names() -> List[str]:
    return __all__


def is_valid_runner_name(runner_name: str) -> bool:
    return runner_name in __all__


def get_runner_human_name(runner_name: str) -> str:
    """Returns a human-readable name for a runner; as a convenience, if the name
    is falsy (None or blank) this returns an empty string. Provides caching for the
    names."""
    if runner_name:
        if runner_name not in _cached_runner_human_names:
            try:
                _cached_runner_human_names[runner_name] = import_runner(runner_name)().human_name
            except InvalidRunnerError:
                _cached_runner_human_names[runner_name] = runner_name  # an obsolete runner
        return _cached_runner_human_names[runner_name]

    return ""
