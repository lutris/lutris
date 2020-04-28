"""Filesystem utilities"""
# Standard Library
import os
import subprocess

# Third Party Libraries
from gi.repository import Gio

# Lutris Modules
from lutris.util.log import logger


def get_mounted_discs():
    """Return a list of mounted discs and ISOs

    :rtype: list of Gio.Mount
    """
    volumes = Gio.VolumeMonitor.get()
    drives = []

    for mount in volumes.get_mounts():
        if mount.get_volume():
            device = mount.get_volume().get_identifier("unix-device")
            if not device:
                logger.debug("No device for mount %s", mount.get_name())
                continue

            # Device is a disk drive or ISO image
            if "/dev/sr" in device or "/dev/loop" in device:
                drives.append(mount.get_root().get_path())
    return drives


def find_mount_point(path):
    """Return the mount point a file is located on"""
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path


def get_mountpoint_drives():
    """Return a mapping of mount points with their corresponding drives"""
    mounts = subprocess.check_output(["mount", "-v"]).decode("utf-8").split("\n")
    mount_map = []
    for mount in mounts:
        mount_parts = mount.split()
        if len(mount_parts) < 3:
            continue
        mount_map.append((mount_parts[2], mount_parts[0]))
    return dict(mount_map)


def get_drive_for_path(path):
    """Return the physical drive a file is located on"""
    return get_mountpoint_drives().get(find_mount_point(path))
