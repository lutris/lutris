from gi.repository import Gio
from lutris.util.log import logger


def get_mounted_discs():
    """Return a list of mounted discs and ISOs

    :rtype: list of Gio.Mount
    """
    vm = Gio.VolumeMonitor.get()
    drives = []

    for mount in vm.get_mounts():
        if mount.get_volume():
            device = mount.get_volume().get_identifier("unix-device")
            if not device:
                logger.debug("No device for mount %s", mount.get_name())
                continue

            # Device is a disk drive or ISO image
            if "/dev/sr" in device or "/dev/loop" in device:
                drives.append(mount.get_root().get_path())
    return drives
