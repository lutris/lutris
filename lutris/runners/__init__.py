"""Generic runner functions"""
from lutris.util.log import logger

__all__ = ("linux", "steam", "wine", "winesteam", "sdlmame", "mednafen", "scummvm",
           "snes9x", "gens", "uae", "fsuae", "nulldc", "openmsx", 'dolphin',
           "dosbox", "pcsxr", "atari800", "mupen64plus", "frotz", "browser",
           "osmose", "vice", "hatari", "stella", "jzintv", "o2em")


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
