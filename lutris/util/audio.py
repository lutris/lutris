"""Whatever it is we want to do with audio module"""
# Standard Library
from __future__ import annotations

import time

# Lutris Modules
from lutris.util import system
from lutris.util.log import logger


def reset_pulse():
    """Reset pulseaudio."""
    if not system.find_executable("pulseaudio"):
        logger.warning("PulseAudio not installed. Nothing to do.")
        return
    system.execute(["pulseaudio", "--kill"])
    time.sleep(1)
    system.execute(["pulseaudio", "--start"])
    logger.debug("PulseAudio restarted")
