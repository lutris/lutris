import subprocess
from lutris.util.log import logger


def reset_pulse():
    """Reset pulseaudio."""
    pulse_reset = "pulseaudio --kill && sleep 1 && pulseaudio --start"
    subprocess.Popen(pulse_reset, shell=True)
    logger.debug("PulseAudio restarted")
