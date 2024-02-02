import glob
import os
import re
import shutil
from typing import Dict

from lutris.util import system
from lutris.util.graphics import drivers
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger

VULKANINFO_AVAILABLE = shutil.which("vulkaninfo")
VULKAN_DATA_DIRS = [
    "/usr/local/etc",  # standard site-local location
    "/usr/local/share",  # standard site-local location
    "/etc",  # standard location
    "/usr/share",  # standard location
    "/usr/lib/x86_64-linux-gnu/GL",  # Flatpak GL extension
    "/usr/lib/i386-linux-gnu/GL",  # Flatpak GL32 extension
    "/opt/amdgpu-pro/etc",  # AMD GPU Pro - TkG
]

GPUS = {}


def get_gpus_info():
    """Return the information related to each GPU on the system"""
    return {card: drivers.get_gpu_info(card) for card in drivers.get_gpu_cards()}


def display_gpu_info(gpu_id, gpu_info):
    """Log GPU information"""
    try:
        gpu_string = f"GPU: {gpu_info['PCI_ID']} {gpu_info['PCI_SUBSYS_ID']} ({gpu_info['DRIVER']} drivers)"
        logger.info(gpu_string)
    except KeyError:
        logger.error("Unable to get GPU information from '%s'", gpu_id)


def add_icd_search_path(paths):
    icd_paths = []
    if paths:
        # unixy env vars with multiple paths are : delimited
        for path in paths.split(":"):
            path = os.path.join(path, "vulkan")
            if os.path.exists(path) and path not in icd_paths:
                icd_paths.append(path)
    return icd_paths


def get_vk_icd_files():
    """Returns available vulkan ICD files in the same search order as vulkan-loader,
    but in a single list"""
    icd_search_paths = []
    for path in VULKAN_DATA_DIRS:
        icd_search_paths += add_icd_search_path(path)
    all_icd_files = []
    for data_dir in icd_search_paths:
        path = os.path.join(data_dir, "icd.d", "*.json")
        # sort here as directory enumeration order is not guaranteed in linux
        # so it's consistent every time
        icd_files = sorted(glob.glob(path))
        if icd_files:
            all_icd_files += icd_files
    return all_icd_files


class GPU:
    def __init__(self, card):
        self.card = card
        self.gpu_info = self.get_gpu_info()
        self.driver = self.gpu_info["DRIVER"]
        self.pci_id = self.gpu_info["PCI_ID"]
        self.pci_subsys_id = self.gpu_info["PCI_SUBSYS_ID"]
        self.pci_slot = self.gpu_info["PCI_SLOT_NAME"]
        self.icd_files = self.get_icd_files()
        if VULKANINFO_AVAILABLE:
            self.name = self.get_vulkaninfo_name()
        else:
            self.name = self.get_lspci_name()

    def __str__(self):
        return f"{self.short_name} ({self.pci_id}:{self.pci_subsys_id} {self.driver})"

    def get_driver_info(self):
        driver_info = {}
        if self.driver == "nvidia":
            driver_info = drivers.get_nvidia_driver_info()
        elif LINUX_SYSTEM.glxinfo:
            if hasattr(LINUX_SYSTEM.glxinfo, "GLX_MESA_query_renderer"):
                driver_info = {
                    "vendor": LINUX_SYSTEM.glxinfo.opengl_vendor,
                    "version": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.version,
                    "device": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.device
                }
        return driver_info

    def get_gpu_info(self) -> Dict[str, str]:
        """Return information about a GPU"""
        infos = {"DRIVER": "", "PCI_ID": "", "PCI_SUBSYS_ID": "", "PCI_SLOT_NAME": ""}
        try:
            with open(
                f"/sys/class/drm/{self.card}/device/uevent", encoding="utf-8"
            ) as card_uevent:
                content = card_uevent.readlines()
        except FileNotFoundError:
            logger.error("Unable to read driver information for card %s", self.card)
            raise
        for line in content:
            key, value = line.split("=", 1)
            infos[key] = value.strip()
        return infos

    def get_vulkaninfo_name(self):
        """Runs vulkaninfo to find the GPU name"""
        subprocess_env = dict(os.environ)
        subprocess_env["VK_DRIVER_FILES"] = self.icd_files  # Currently supported
        subprocess_env["VK_ICD_FILENAMES"] = self.icd_files  # Deprecated
        vulkaninfo_output = system.read_process_output(
            "vulkaninfo", env=subprocess_env
        ).split("\n")
        result = ""
        for line in vulkaninfo_output:
            if "deviceName" not in line:
                continue
            result = line.split("= ", maxsplit=1)[1].strip()
        if (
            "Failed to detect any valid GPUs" in result
            or "ERROR: [Loader Message]" in result
        ):
            return "No GPU"
        return result

    def get_lspci_name(self):
        devices = [
            (pci_id, device_desc.split(": ")[1])
            for pci_id, device_desc in [
                line.split(maxsplit=1)
                for line in system.execute("lspci", timeout=3).split("\n")
            ]
        ]
        for device in devices:
            if f"0000:{device[0]}" == self.pci_slot:
                return device[1]

    def get_icd_files(self):
        loader = self.driver
        loader_map = {
            "amdgpu": "radeon",
            "vc4-drm": "broadcom",
        }
        if self.driver in loader_map:
            loader = loader_map[self.driver]
        icd_files = []
        for icd_file in get_vk_icd_files():
            if loader in icd_file:
                icd_files.append(icd_file)
        return ":".join(icd_files)

    @property
    def short_name(self):
        """Shorten result to just the friendly name of the GPU
        vulkaninfo returns Vendor Friendly Name (Chip Developer Name)
        AMD Radeon Pro W6800 (RADV NAVI21) -> AMD Radeon Pro W6800"""
        return re.sub(r"\s*\(.*?\)", "", self.name)
