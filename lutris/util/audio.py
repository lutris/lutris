"""Whatever it is we want to do with audio module"""
import subprocess
import time
from lutris.util.log import logger


def reset_pulse():
    """Reset pulseaudio."""
    subprocess.Popen(["pulseaudio", "--kill"])
    time.sleep(1)
    subprocess.Popen(["pulseaudio", "--start"])
    logger.debug("PulseAudio restarted")
