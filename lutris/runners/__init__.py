__all__  = ["linux", "wine", 'steam',"sdlmame", "mednafen", "scummvm",
            "snes9x", "gens", "uae", "nulldc", "openmsx", 'dolphin', "dosbox",
            "pcsx", "atari800", "mupen64plus", "frotz", "browser", 'osmose',
            'vice', 'hatari', 'stella', 'jzintv', 'o2em']


def import_runner(runner_name, config=None):
    try:
        runner_module = __import__('lutris.runners.%s' % runner_name,
                                globals(), locals(), [runner_name], -1)
        runner_cls = getattr(runner_module, runner_name)
    except ImportError, msg:
        from lutris.util.log import logger
        logger.error("Invalid runner %s" % runner)
        logger.error(msg)

    return runner_cls(config)
