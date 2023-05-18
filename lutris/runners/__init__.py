"""Runner loaders"""

__all__ = [
    # Native
    "linux",
    "steam",
    "web",
    "flatpak",
    # Microsoft based
    "wine",
    "dosbox",
    "xemu",
    # Multi-system
    "easyrpg",
    "mame",
    "mednafen",
    "scummvm",
    "libretro",
    # Commodore
    "fsuae",
    "vice",
    # Atari
    "atari800",
    "hatari",
    # Nintendo
    "snes9x",
    "mupen64plus",
    "dolphin",
    "ryujinx",
    "yuzu",
    # Sony
    "pcsx2",
    "rpcs3",
    # Sega
    "osmose",
    "reicast",
    "redream",
    # Fantasy consoles
    "pico8",
    # Misc legacy systems
    "jzintv",
    "o2em",
    "zdoom",
]

ADDON_RUNNERS = {}
_cached_runner_human_names = {}


class InvalidRunner(Exception):

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class RunnerInstallationError(Exception):

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class NonInstallableRunnerError(Exception):

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def get_runner_module(runner_name):
    if runner_name not in __all__:
        raise InvalidRunner("Invalid runner name '%s'" % runner_name)
    return __import__("lutris.runners.%s" % runner_name, globals(), locals(), [runner_name], 0)


def import_runner(runner_name):
    """Dynamically import a runner class."""
    if runner_name in ADDON_RUNNERS:
        return ADDON_RUNNERS[runner_name]

    runner_module = get_runner_module(runner_name)
    if not runner_module:
        return None
    return getattr(runner_module, runner_name)


def import_task(runner, task):
    """Return a runner task."""
    runner_module = get_runner_module(runner)
    if not runner_module:
        return None
    return getattr(runner_module, task)


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
        ADDON_RUNNERS[runner_name] = runners[runner_name]
        __all__.append(runner_name)
    _cached_runner_human_names.clear()


def get_runner_names():
    return __all__


def get_runner_human_name(runner_name):
    """Returns a human-readable name for a runner; as a convenience, if the name
    is falsy (None or blank) this returns an empty string. Provides caching for the
    names."""
    if runner_name:
        if runner_name not in _cached_runner_human_names:
            try:
                _cached_runner_human_names[runner_name] = import_runner(runner_name)().human_name
            except InvalidRunner:
                _cached_runner_human_names[runner_name] = runner_name  # an obsolete runner
        return _cached_runner_human_names[runner_name]

    return ""
