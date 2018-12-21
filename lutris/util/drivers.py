"""Hardware driver related utilities

Everything in this module should rely on /proc or /sys only, no executable calls
"""
import os
import re
from lutris.util.log import logger


def get_nvidia_driver_info():
    """Return information about NVidia drivers"""
    with open("/proc/driver/nvidia/version") as version_file:
        content = version_file.readlines()
    nvrm_version = content[0].split(': ')[1].strip().split()
    gcc_version = content[1].split(': ')[1].strip().split()

    return {
        'nvrm': {
            'vendor': nvrm_version[0],
            'platform': nvrm_version[1],
            'arch': nvrm_version[2],
            'version': nvrm_version[5],
            'date': ' '.join(nvrm_version[6:])
        },
        'gcc': {
            'version': gcc_version[2],
            'platform': ' '.join(gcc_version[3:]).strip('()')
        }
    }


def get_nvidia_gpu_ids():
    """Return the list of Nvidia GPUs"""
    return os.listdir("/proc/driver/nvidia/gpus")


def get_nvidia_gpu_info(gpu_id):
    """Return details about a GPU"""
    with open("/proc/driver/nvidia/gpus/%s/information" % gpu_id) as info_file:
        content = info_file.readlines()
    infos = {}
    for line in content:
        key, value = line.split(":", 1)
        infos[key] = value.strip()
    return infos


def is_nvidia():
    """Return true if the Nvidia drivers are currently in use"""
    return os.path.exists("/proc/driver/nvidia")


def get_gpus():
    """Return GPUs connected to the system"""
    if not os.path.exists("/sys/class/drm"):
        logger.error("No GPU available on this system!")
        return
    for cardname in os.listdir("/sys/class/drm/"):
        if re.match(r"^card\d$", cardname):
            yield cardname


def get_gpu_info(card):
    """Return information about a GPU"""
    with open("/sys/class/drm/%s/device/uevent" % card) as card_uevent:
        content = card_uevent.readlines()
    infos = {}
    for line in content:
        key, value = line.split("=", 1)
        infos[key] = value.strip()
    return infos


def is_amd():
    """Return true if the system uses the AMD driver"""
    for card in get_gpus():
        if get_gpu_info(card)["DRIVER"] == "amdgpu":
            return True


def check_driver():
    """Report on the currently running driver"""
    if is_nvidia():
        driver_info = get_nvidia_driver_info()
        # pylint: disable=logging-format-interpolation
        logger.info("Using {vendor} drivers {version} for {arch}".format(**driver_info["nvrm"]))
        gpus = get_nvidia_gpu_ids()
        for gpu_id in gpus:
            gpu_info = get_nvidia_gpu_info(gpu_id)
            logger.info("GPU: %s", gpu_info.get("Model"))
    for card in get_gpus():
        # pylint: disable=logging-format-interpolation
        logger.info(
            "GPU: {PCI_ID} {PCI_SUBSYS_ID} using {DRIVER} driver".format(**get_gpu_info(card))
        )
