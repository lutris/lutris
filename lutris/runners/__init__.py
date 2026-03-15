"""Runner loaders"""

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

from typing import Callable

from lutris.exceptions import LutrisError, MisconfigurationError

ADDON_RUNNERS = {}
_cached_runner_human_names = {}


class InvalidRunnerError(MisconfigurationError):
    """Raise if a runner name is used that is not known to Lutris."""


class RunnerInstallationError(LutrisError):
    """Raised if the attempt to install a runner fails, perhaps because
    of invalid data from a server."""


class NonInstallableRunnerError(LutrisError):
    """Raised if installed a runner that Lutris cannot install, like Flatpak.
    These must be installed separately."""


def get_runner_module(runner_name):
    if not is_valid_runner_name(runner_name):
        raise InvalidRunnerError("Invalid runner name '%s'" % runner_name)
    module = __import__("lutris.runners.%s" % runner_name, globals(), locals(), [runner_name], 0)
    if not module:
        raise InvalidRunnerError("Runner module for '%s' could not be imported." % runner_name)
    return module


def get_runner_command_module(runner_name):
    if not is_valid_runner_name(runner_name):
        raise InvalidRunnerError("Invalid runner name '%s'" % runner_name)
    module = __import__("lutris.runners.commands.%s" % runner_name, globals(), locals(), [runner_name], 0)
    if not module:
        raise InvalidRunnerError("No runner commands exist for '%s'." % runner_name)
    return module


def import_runner(runner_name):
    """Dynamically import a runner class."""
    if runner_name in ADDON_RUNNERS:
        return ADDON_RUNNERS[runner_name]

    runner_module = get_runner_module(runner_name)
    return getattr(runner_module, runner_name)


def import_task(runner: str, task: str) -> Callable | None:
    """Return a runner command task, and verifies that it is defined exactly by
    the command module, not something it imports."""
    try:
        runner_module = get_runner_command_module(runner)
        func = getattr(runner_module, task)
        if func.__module__ == runner_module.__name__:
            return func
        return None
    except (AttributeError, InvalidRunnerError):
        return None


def get_installed(sort=True):
    """Return a list of installed runners (class instances)."""
    installed = []
    for runner_name in __all__:
        runner = import_runner(runner_name)()
        if runner.is_installed():
            installed.append(runner)
    return sorted(installed) if sort else installed


def inject_runners(runners):
    for runner_name in runners:
        if runner_name not in __all__:
            ADDON_RUNNERS[runner_name] = runners[runner_name]
            __all__.append(runner_name)
    _cached_runner_human_names.clear()


def get_runner_names():
    return __all__


def is_valid_runner_name(runner_name: str) -> bool:
    return runner_name in __all__


def get_runner_human_name(runner_name):
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
