"""Generic runner functions"""
__all__ = ["linux", "wine", 'steam', "sdlmame", "mednafen", "scummvm",
            "snes9x", "gens", "uae", "nulldc", "openmsx", 'dolphin', "dosbox",
            "pcsx", "atari800", "mupen64plus", "frotz", "browser", 'osmose',
            'vice', 'hatari', 'stella', 'jzintv', 'o2em']


def import_runner(runner_name, config=None):
    """Dynamically import a runner class"""
    try:
        runner_module = __import__('lutris.runners.%s' % runner_name,
                                globals(), locals(), [runner_name], -1)
        runner_cls = getattr(runner_module, runner_name)
    except ImportError, msg:
        from lutris.util.log import logger
        logger.error("Invalid runner %s" % runner_name)
        logger.error(msg)
    return runner_cls(config)


def import_task(runner, task):
    """Return a runner task"""
    try:
        runner_module = __import__('lutris.runners.%s' % runner,
                                globals(), locals(), [runner], -1)
        runner_task = getattr(runner_module, task)
    except ImportError, msg:
        from lutris.util.log import logger
        logger.error("Invalid runner %s" % runner)
        logger.error(msg)
    return runner_task
