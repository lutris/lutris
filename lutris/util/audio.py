"""Whatever it is we want to do with audio module"""
import time
from lutris.util.log import logger
from lutris.util import system


def reset_pulse():
    """Reset pulseaudio."""
    if not system.find_executable("pulseaudio"):
        logger.warning("PulseAudio not installed. Nothing to do.")
        return
    system.execute(["pulseaudio", "--kill"])
    time.sleep(1)
    system.execute(["pulseaudio", "--start"])
    logger.debug("PulseAudio restarted")
