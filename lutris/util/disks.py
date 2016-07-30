from gi.repository import Gio
from lutris.util.log import logger


def get_mounted_discs():
    """Return a list of mounted discs and ISOs

    :rtype: list of Gio.Mount
    """
    vm = Gio.VolumeMonitor.get()
    drives = []

    for m in vm.get_mounts():
        if m.get_volume():
            device = m.get_volume().get_identifier('unix-device')
            if not device:
                logger.debug("No device for mount %s", m.get_name())
                continue

            # Device is a disk drive or ISO image
            if '/dev/sr' in device or '/dev/loop' in device:
                drives.append(m)
    return drives
