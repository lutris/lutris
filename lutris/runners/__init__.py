"""Generic runner functions"""
from lutris.util.log import logger

__all__ = (
    # Native
    "linux", "steam", "browser", "desura",
    # Microsoft based
    "wine", "winesteam", "dosbox",
    # Multi-system
    "mame", "mess", "scummvm", "mednafen",
    # Commdore
    "fsuae", "vice",
    # Atari
    "stella", "atari800", "hatari", "virtualjaguar",
    # Nintendo
    "snes9x",  "mupen64plus",  # "dolphin",
    # Sony
    "pcsxr",
    # Sega
    "osmose", "gens", "nulldc",
    # Misc legacy systems
    "openmsx", "frotz", "jzintv", "o2em",
)


def get_runner_module(runner_name):
    if not runner_name:
        raise ValueError("Missing runner name")
    if runner_name not in __all__:
        logger.error("Invalid runner name '%s'", runner_name)
        return False
    return __import__('lutris.runners.%s' % runner_name,
                      globals(), locals(), [runner_name], -1)


def import_runner(runner_name):
    """Dynamically import a runner class"""
    runner_module = get_runner_module(runner_name)
    if not runner_module:
        return
    return getattr(runner_module, runner_name)


def import_task(runner, task):
    """Return a runner task"""
    runner_module = get_runner_module(runner)
    if not runner_module:
        return
    return getattr(runner_module, task)
