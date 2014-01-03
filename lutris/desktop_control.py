#!/usr/bin/python
# -*- coding:Utf-8 -*-
""" Utilities to control the user's desktop in many aspects

    This class interacts with the window manager, xrandr, ...
"""

import os
import subprocess

from lutris.util.log import logger


def get_resolutions():
    """Return the list of supported screen resolutions."""
    xrandr_output = subprocess.Popen("xrandr",
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE).communicate()[0]
    resolution_list = []
    for line in xrandr_output.split("\n"):
        if line.startswith("  "):
            resolution_list.append(line.split()[0])
    return resolution_list


def get_current_resolution():
    """Return the current resolution for the desktop."""
    xrandr_output = subprocess.Popen("xrandr",
                                     stdout=subprocess.PIPE).communicate()[0]
    for line in xrandr_output.split("\n"):
        if line.startswith("  ") and "*" in line:
            return line.split()[0]
    return None


def change_resolution(resolution):
    """change desktop resolution"""
    logger.debug("Switching resolution to %s", resolution)
    if resolution not in get_resolutions():
        logger.warning("Resolution %s doesn't exist.")
    else:
        subprocess.Popen("xrandr -s %s" % resolution, shell=True)


def check_joysticks():
    """Return list of connected joysticks."""
    number_joysticks = 0
    joysticks = []
    for device_number in range(0, 8):
        device_name = "/dev/input/js%d" % device_number
        if os.path.exists(device_name):
            number_joysticks = number_joysticks + 1
            joysticks.append(device_name)
    return joysticks


def reset_desktop():
    """Restore the desktop to its original state."""
    #Restore resolution
    resolution = get_resolutions()[0]
    change_resolution(resolution)
    #Restore gamma
    os.popen("xgamma -gamma 1.0")


def reset_pulse():
    """ Reset pulseaudio. """
    pulse_reset = "pulseaudio --kill && sleep 1 && pulseaudio --start"
    subprocess.Popen(pulse_reset, shell=True)
    logger.debug("PulseAudio restarted")
