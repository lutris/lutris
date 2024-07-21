# pylint: disable=no-member
"""Hardware driver related utilities

Everything in this module should rely on /proc or /sys only, no executable calls
"""

import os
import re
from typing import Dict, Iterable, List

from lutris.util import cache_single
from lutris.util.graphics.glxinfo import GlxInfo
from lutris.util.log import logger
from lutris.util.system import read_process_output

MIN_RECOMMENDED_NVIDIA_DRIVER = 515


@cache_single
def get_nvidia_driver_info() -> Dict[str, Dict[str, str]]:
    """Return information about Nvidia drivers"""
    version_file_path = "/proc/driver/nvidia/version"

    def read_from_proc() -> Dict[str, Dict[str, str]]:
        try:
            if not os.path.exists(version_file_path):
                return {}
            with open(version_file_path, encoding="utf-8") as version_file:
                content = version_file.readlines()
        except PermissionError:
            # MAC systems (selinux, apparmor) may block access to files in /proc.
            # If this happens, we may still be able to retrieve the info by
            # other means, but need additional validation.
            logger.info("Could not access %s. Falling back to glxinfo.", version_file_path)
            return {}
        except OSError as e:
            logger.warning(
                "Unexpected error when accessing %s. Falling back to glxinfo.",
                version_file_path,
                exc_info=e,
            )
            return {}

        try:
            nvrm_version = content[0].split(": ")[1].strip().split()
            if "Open" in nvrm_version:
                return {
                    "vendor": nvrm_version[0],
                    "platform": nvrm_version[1],
                    "arch": nvrm_version[6],
                    "version": nvrm_version[7],
                }
            return {
                "vendor": nvrm_version[0],
                "platform": nvrm_version[1],
                "arch": nvrm_version[2],
                "version": nvrm_version[5],
                "date": " ".join(nvrm_version[6:]),
            }
        except IndexError as ex:
            logger.warning("Unable to parse %s. Falling back to glxinfo: %s", version_file_path, ex)
            return {}

    def invoke_glxinfo() -> Dict[str, Dict[str, str]]:
        glx_info = GlxInfo()
        platform = read_process_output(["uname", "-s"])
        arch = read_process_output(["uname", "-m"])
        vendor = glx_info.opengl_vendor  # type: ignore[attr-defined]
        if "nvidia" not in vendor.lower():
            raise RuntimeError("Expected NVIDIA vendor information, received %s." % vendor)
        return {
            "vendor": vendor,
            "platform": platform,
            "arch": arch,
            "version": glx_info.opengl_version.rsplit(maxsplit=1)[-1],  # type: ignore[attr-defined]
        }

    try:
        from_proc = read_from_proc()
        if from_proc:
            return from_proc
    except Exception as ex:
        logger.exception("Unable to read from '%s': %s", version_file_path, ex)

    return invoke_glxinfo()


def get_nvidia_gpu_ids() -> List[str]:
    """Return the list of Nvidia GPUs"""
    gpus_dir = "/proc/driver/nvidia/gpus"
    try:
        return os.listdir(gpus_dir)
    except PermissionError:
        logger.info("Permission denied to %s. Using lspci instead.", gpus_dir)
    except OSError as e:
        logger.warning("Unexpected error accessing %s. Using lspci instead.", gpus_dir, exc_info=e)
    # 10de is NVIDIA's vendor ID, 0300 gets you video controllers.
    values = read_process_output(["lspci", "-D", "-n", "-d", "10de::0300"]).splitlines()
    return [line.split(maxsplit=1)[0] for line in values]


def get_nvidia_gpu_info(gpu_id: str) -> Dict[str, str]:
    """Return details about a GPU"""
    gpu_info_file = f"/proc/driver/nvidia/gpus/{gpu_id}/information"
    try:
        with open(gpu_info_file, encoding="utf-8") as info_file:
            content = info_file.readlines()
    except PermissionError:
        logger.info("Permission denied to %s. Detecting with lspci.", gpu_info_file)
    except OSError as e:
        logger.warning(
            "Unexpected error accessing %s. Detecting with lspci",
            gpu_info_file,
            exc_info=e,
        )
    else:
        info = {}
        for line in content:
            key, value = line.split(":", 1)
            info[key] = value.strip()
        return info
    return get_lspci_nvidia_gpu_info(gpu_id)


def get_lspci_nvidia_gpu_info(gpu_id: str) -> Dict[str, str]:
    lspci_data = read_process_output(["lspci", "-v", "-s", gpu_id])
    model_info = re.search(r"NVIDIA Corporation \w+ \[(.+?)\]", lspci_data)
    if model_info:
        model = model_info.group(1)
    else:
        logger.error("Could not detect NVIDIA GPU model.")
        model = "Unknown"
    irq_info = re.search("IRQ ([0-9]+)", lspci_data)
    if irq_info:
        irq = irq_info.group(1)
    else:
        logger.error("Could not detect GPU IRQ information.")
        irq = None

    info = {
        "Model": f"NVIDIA {model}",
        "IRQ": str(irq),
        "Bus Location": str(gpu_id),
    }
    for line in lspci_data.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip()] = value.strip()
    return info


def is_nvidia() -> bool:
    """Return true if the Nvidia drivers are currently in use.

    Note: This function may not detect use of the nouveau drivers.
    """

    try:
        return os.path.exists("/proc/driver/nvidia")
    except OSError:
        logger.info("Could not determine whether /proc/driver/nvidia exists. " "Falling back to alternative method")
    try:
        with open("/proc/modules", encoding="utf-8") as f:
            modules = f.read()
        return bool(re.search(r"^nvidia ", modules, flags=re.MULTILINE))
    except OSError:
        logger.error("Could not access /proc/modules to find the Nvidia drivers. " "Nvidia card may not be detected.")
    glx_info = GlxInfo()
    return "NVIDIA" in glx_info.opengl_vendor  # type: ignore[attr-defined]


def get_gpu_cards() -> Iterable[str]:
    """Return GPUs connected to the system"""
    if not os.path.exists("/sys/class/drm"):
        logger.error("No GPU available on this system!")
        return

    try:
        cardlist = os.listdir("/sys/class/drm/")
    except PermissionError:
        logger.error("Your system does not allow reading from /sys/class/drm, no GPU detected.")
        return

    for cardname in cardlist:
        if re.match(r"^card\d$", cardname):
            yield cardname


def get_gpu_info(card: str) -> Dict[str, str]:
    """Return information about a GPU"""
    infos = {"DRIVER": "", "PCI_ID": "", "PCI_SUBSYS_ID": ""}
    try:
        with open(f"/sys/class/drm/{card}/device/uevent", encoding="utf-8") as card_uevent:
            content = card_uevent.readlines()
    except FileNotFoundError:
        logger.error("Unable to read driver information for card %s", card)
        return infos
    for line in content:
        key, value = line.split("=", 1)
        infos[key] = value.strip()
    return infos


def is_amd() -> bool:
    """Return true if the system uses the AMD driver"""
    for card in get_gpu_cards():
        if get_gpu_info(card)["DRIVER"] == "amdgpu":
            return True
    return False


def is_outdated() -> bool:
    if not is_nvidia():
        return False
    driver_info = get_nvidia_driver_info()
    driver_version = driver_info["version"]
    if not driver_version:
        logger.error("Failed to get Nvidia version")
        return True
    try:
        major_version = int(driver_version.split(".")[0])
    except (IndexError, ValueError) as ex:
        logger.exception("Failed to parse Nvidia version: %s", ex)
        return True
    return major_version < MIN_RECOMMENDED_NVIDIA_DRIVER
