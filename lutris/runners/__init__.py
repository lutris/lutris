"""Generic runner functions."""
# from lutris.util.log import logger

__all__ = (
    # Native
    "linux",
    "steam",
    "browser",
    "web",
    # Microsoft based
    "wine",
    "winesteam",
    "dosbox",
    # Multi-system
    "mame",
    "mess",
    "mednafen",
    "scummvm",
    "residualvm",
    "libretro",
    "ags",
    "higan",
    # Commdore
    "fsuae",
    "vice",
    # Atari
    "stella",
    "atari800",
    "hatari",
    "virtualjaguar",
    # Nintendo
    "snes9x",
    "mupen64plus",
    "dolphin",
    "desmume",
    "citra",
    "melonds",
    # Sony
    "ppsspp",
    "pcsx2",
    "rpcs3",
    # Sega
    "osmose",
    "dgen",
    "reicast",
    "redream",
    # Fantasy consoles
    "pico8",
    # Misc legacy systems
    "frotz",
    "jzintv",
    "o2em",
    "zdoom",
    "tic80",
)


class InvalidRunner(Exception):
    def __init__(self, message):
        self.message = message


class RunnerInstallationError(Exception):
    def __init__(self, message):
        self.message = message


class NonInstallableRunnerError(Exception):
    def __init__(self, message):
        self.message = message


def get_runner_module(runner_name):
    if runner_name not in __all__:
        raise InvalidRunner("Invalid runner name '%s'" % runner_name)
    return __import__(
        "lutris.runners.%s" % runner_name, globals(), locals(), [runner_name], 0
    )


def import_runner(runner_name):
    """Dynamically import a runner class."""
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
