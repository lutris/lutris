"""Hardware driver related utilities

Everything in this module should rely on /proc or /sys only, no executable calls
"""
import contextlib
import os
import re
from typing import Dict, Iterable, List

from lutris.util.graphics.glxinfo import GlxInfo
from lutris.util.log import logger
from lutris.util.system import read_process_output

MIN_RECOMMENDED_NVIDIA_DRIVER = 415


def get_nvidia_driver_info() -> Dict[str, Dict[str, str]]:
    """Return information about NVidia drivers"""
    version_file_path = "/proc/driver/nvidia/version"
    if not os.path.exists(version_file_path):
        return {}
    with contextlib.suppress(OSError):
        with open(version_file_path, encoding="utf-8") as version_file:
            content = version_file.readlines()
        nvrm_version = content[0].split(": ")[1].strip().split()
        if "Open" in nvrm_version:
            return {
                "nvrm": {
                    "vendor": nvrm_version[0],
                    "platform": nvrm_version[1],
                    "arch": nvrm_version[6],
                    "version": nvrm_version[7],
                }
            }
        return {
            "nvrm": {
                "vendor": nvrm_version[0],
                "platform": nvrm_version[1],
                "arch": nvrm_version[2],
                "version": nvrm_version[5],
                "date": " ".join(nvrm_version[6:]),
            }
        }
    # If the /proc file failed, look it up with glxinfo.
    glx_info = GlxInfo()
    platform = read_process_output(["uname", "-s"])
    arch = read_process_output(["uname", "-m"])
    return {
        "nvrm": {
            "vendor": glx_info.opengl_vendor,  # type: ignore[attr-defined]
            "platform": platform,
            "arch": arch,
            "version": glx_info.opengl_version.rsplit(maxsplit=1)[-1],  # type: ignore[attr-defined]
        }
    }


def get_nvidia_gpu_ids() -> List[str]:
    """Return the list of Nvidia GPUs"""
    with contextlib.suppress(OSError):
        return os.listdir("/proc/driver/nvidia/gpus")
    values = read_process_output(
        # 10de is NVIDIA's vendor ID, 0300 gets you video controllers.
        ["lspci", "-D", "-n", "-d", "10de::0300"],
    ).splitlines()
    return [line.split(maxsplit=1)[0] for line in values]


def get_nvidia_gpu_info(gpu_id: str) -> Dict[str, str]:
    """Return details about a GPU"""
    with contextlib.suppress(OSError):
        with open(
            "/proc/driver/nvidia/gpus/%s/information" % gpu_id, encoding="utf-8"
        ) as info_file:
            content = info_file.readlines()
        infos = {}
        for line in content:
            key, value = line.split(":", 1)
            infos[key] = value.strip()
        return infos
    lspci_data = read_process_output(["lspci", "-v", "-s", gpu_id])
    model_info = re.search(r"NVIDIA Corporation \w+ \[(.+?)\]", lspci_data)
    if model_info:
        model = model_info.group(1)
    irq_info = re.search("IRQ ([0-9]+)", lspci_data)
    if irq_info:
        irq = irq_info.group(1)

    info = {
        "Model": f"NVIDIA {model}",
        "IRQ": irq,
        "Bus Location": gpu_id,
    }
    for line in lspci_data.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip()] = value.strip()
    return info


def is_nvidia() -> bool:
    """Return true if the Nvidia drivers are currently in use"""
    with contextlib.suppress(OSError):
        return os.path.exists("/proc/driver/nvidia")
    with contextlib.suppress(OSError):
        with open("/proc/modules") as f:
            modules = f.read()
        return bool(re.search(r"^nvidia ", modules, flags=re.MULTILINE))
    glx_info = GlxInfo()
    return "NVIDIA" in glx_info.opengl_vendor  # type: ignore[attr-defined]


def get_gpus() -> Iterable[str]:
    """Return GPUs connected to the system"""
    if not os.path.exists("/sys/class/drm"):
        logger.error("No GPU available on this system!")
        return []
    try:
        cardlist = os.listdir("/sys/class/drm/")
    except PermissionError:
        logger.error(
            "Your system does not allow reading from /sys/class/drm, no GPU detected."
        )
        return
    for cardname in cardlist:
        if re.match(r"^card\d$", cardname):
            yield cardname


def get_gpu_info(card: str) -> Dict[str, str]:
    """Return information about a GPU"""
    infos = {"DRIVER": "", "PCI_ID": "", "PCI_SUBSYS_ID": ""}
    try:
        with open(
            "/sys/class/drm/%s/device/uevent" % card, encoding="utf-8"
        ) as card_uevent:
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
    for card in get_gpus():
        if get_gpu_info(card)["DRIVER"] == "amdgpu":
            return True
    return False


def check_driver() -> None:
    """Report on the currently running driver"""
    if is_nvidia():
        driver_info = get_nvidia_driver_info()
        # pylint: disable=logging-format-interpolation
        logger.info(
            "Using {vendor} drivers {version} for {arch}".format(**driver_info["nvrm"])
        )
        gpus = get_nvidia_gpu_ids()
        for gpu_id in gpus:
            gpu_info = get_nvidia_gpu_info(gpu_id)
            logger.info("GPU: %s", gpu_info.get("Model"))
    for card in get_gpus():
        # pylint: disable=logging-format-interpolation
        logger.info(
            "GPU: {PCI_ID} {PCI_SUBSYS_ID} using {DRIVER} driver".format(
                **get_gpu_info(card)
            )
        )


def is_outdated() -> bool:
    if not is_nvidia():
        return False
    driver_info = get_nvidia_driver_info()
    driver_version = driver_info["nvrm"]["version"]
    if not driver_version:
        logger.error("Failed to get Nvidia version")
        return True
    major_version = int(driver_version.split(".")[0])
    return major_version < MIN_RECOMMENDED_NVIDIA_DRIVER
