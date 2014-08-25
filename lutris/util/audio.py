import os
import sys
import subprocess
from lutris.util.log import logger


def get_oss_wrapper(wrapper_type):
    """ Return OSS wrapper to be used.
        padsp32 returns the version shipped with Lutris specifically for some
        32bit games.
    """
    if wrapper_type == 'none':
        return False

    if wrapper_type not in ('padsp', 'padsp32', 'aoss', 'pasuspender'):
        logger.warning("Unsupported OSS wrapper: '%s'", wrapper_type)
        return False

    if wrapper_type == 'padsp32':
        launch_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.join(launch_dir, 'padsp32')
    return wrapper_type


def reset_pulse():
    """ Reset pulseaudio. """
    pulse_reset = "pulseaudio --kill && sleep 1 && pulseaudio --start"
    subprocess.Popen(pulse_reset, shell=True)
    logger.debug("PulseAudio restarted")
