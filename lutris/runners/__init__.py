"""Generic runner functions."""
# from lutris.util.log import logger

__all__ = (
    # Native
    "linux", "steam", "browser", "desura",
    # Microsoft based
    "wine", "winesteam", "dosbox",
    # Multi-system
    "mame", "mess", "mednafen", "scummvm", "residualvm",
    # Commdore
    "fsuae", "vice",
    # Atari
    "stella", "atari800", "hatari", "virtualjaguar",
    # Nintendo
    "snes9x",  "mupen64plus", "dolphin",
    # Sony
    "pcsxr", "ppsspp", "pcsx2",
    # Sega
    "osmose", "dgen", "reicast",
    # Misc legacy systems
    "frotz", "jzintv", "o2em",
)


class InvalidRunner(Exception):
    pass


class RunnerInstallationError(Exception):
    pass


class NonInstallableRunnerError(Exception):
    pass


def get_runner_module(runner_name):
    if runner_name not in __all__:
        raise InvalidRunner("Invalid runner name '%s'", runner_name)
    return __import__('lutris.runners.%s' % runner_name,
                      globals(), locals(), [runner_name], -1)


def import_runner(runner_name):
    """Dynamically import a runner class."""
    runner_module = get_runner_module(runner_name)
    if not runner_module:
        return
    return getattr(runner_module, runner_name)


def import_task(runner, task):
    """Return a runner task."""
    runner_module = get_runner_module(runner)
    if not runner_module:
        return
    return getattr(runner_module, task)


def get_installed(sort=True):
    """Return a list of installed runners (class instances)."""
    installed = []
    for runner_name in __all__:
        runner = import_runner(runner_name)()
        if runner.is_installed():
            installed.append(runner)
    return sorted(installed) if sort else installed
