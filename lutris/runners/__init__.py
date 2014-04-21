"""Generic runner functions"""
from lutris.util.log import logger

__all__ = (
    # Native
    "linux", "steam", "browser",  "desura",
    # Microsoft based
    "wine", "winesteam", "dosbox",
    # Multi-system
    "sdlmame", "sdlmess", "scummvm", "mednafen",
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

def import_runner(runner_name):
    """Dynamically import a runner class"""
    try:
        runner_module = __import__('lutris.runners.%s' % runner_name,
                                   globals(), locals(), [runner_name], -1)
        runner_cls = getattr(runner_module, runner_name)
    except ImportError:
        logger.error("Invalid runner %s" % runner_name)
        raise
    return runner_cls


def import_task(runner, task):
    """Return a runner task"""
    try:
        runner_module = __import__('lutris.runners.%s' % runner,
                                   globals(), locals(), [runner], -1)
        runner_task = getattr(runner_module, task)
    except ImportError:
        logger.error("Invalid runner %s" % runner)
        raise
    return runner_task
