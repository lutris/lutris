#!/usr/bin/python
# -*- coding:Utf-8 -*-
""" Utilities to control the user's desktop in many aspects

    This class interacts with the window manager, xrandr, gconf, ...
"""

import sys
import os.path
import subprocess

from lutris.gconf import GConfSetting
from lutris.util.log import logger


def make_compiz_rule(class_=None, title=None):
    """Return a string formated for the Window Rules plugin"""
    if class_ is not None:
        rule = 'class=%s' % class_
    elif title is not None:
        rule = 'title=%s' % title
    else:
        rule = False
    return rule


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


def set_compiz_nodecoration(klass=None, title=None):
    """Remove the decorations for the game's window"""
    window_rule = make_compiz_rule(klass, title)
    if not window_rule:
        return False
    rule = "(any) & !(%s)" % window_rule
    compiz_root = "/apps/compiz/plugins"
    key = compiz_root + "/decoration/allscreens/options/decoration_match"
    setting = GConfSetting(key, bool)
    setting.set_value(rule)
    return True


def set_compiz_fullscreen(klass=None, title=None):
    """Set a fullscreen rule for the plugin Window Rules"""
    rule = make_compiz_rule(klass, title)
    if not rule:
        return False
    compiz_root = "/apps/compiz/plugins"
    key = compiz_root + "/winrules/screen0/options/fullscreen_match"
    setting = GConfSetting(key, bool)
    setting.set_value(rule)
    return True


def set_keyboard_repeat(value=False):
    """Desactivate key repeats.

    This is needed, for example, in Wolfenstein (2009)
    """
    key = "/desktop/gnome/peripherals/keyboard/repeat"
    setting = GConfSetting(key, bool)
    setting.set_key(key, value)
    return True


def reset_desktop():
    """Restore the desktop to its original state."""
    #Restore resolution
    resolution = get_resolutions()[0]
    change_resolution(resolution)
    #Restore gamma
    os.popen("xgamma -gamma 1.0")


def setup_padsp(setting, command):
    command = command.split()[0]
    if setting == 'padsp32':
        launch_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.join(launch_dir, 'padsp32')
    elif setting == 'padsp':
        return 'padsp'


def reset_pulse():
    """ Reset pulseaudio. """
    pulse_reset = "pulseaudio --kill && sleep 1 && pulseaudio --start"
    subprocess.Popen(pulse_reset, shell=True)
    logger.debug("PulseAudio restarted")
