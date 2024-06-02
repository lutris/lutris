import glob
import os
import re
import shutil
import subprocess
from typing import Dict, Optional

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
        self.pci_id = self.gpu_info["PCI_ID"].lower()
        self.pci_subsys_id = self.gpu_info["PCI_SUBSYS_ID"].lower()
        self.pci_slot = self.gpu_info["PCI_SLOT_NAME"]
        self.icd_files = self.get_icd_files()
        if VULKANINFO_AVAILABLE:
            try:
                self.name = self.get_vulkaninfo_name() or self.get_lspci_name()
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # already logged this, so we'll just fall back to lspci.
                self.name = self.get_lspci_name()
        else:
            self.name = self.get_lspci_name()

    def __str__(self):
        if self.pci_id:
            return f"{self.short_name} ({self.pci_id} {self.pci_subsys_id} {self.driver})"

        return f"{self.short_name} ({self.driver})"

    def get_driver_info(self):
        driver_info = {}
        if self.driver == "nvidia":
            driver_info = drivers.get_nvidia_driver_info()
        elif LINUX_SYSTEM.glxinfo:
            if hasattr(LINUX_SYSTEM.glxinfo, "GLX_MESA_query_renderer"):
                driver_info = {
                    "vendor": LINUX_SYSTEM.glxinfo.opengl_vendor,
                    "version": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.version,
                    "device": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.device,
                }
        return driver_info

    def get_gpu_info(self) -> Dict[str, str]:
        """Return information about a GPU"""
        infos = {"DRIVER": "", "PCI_ID": "", "PCI_SUBSYS_ID": "", "PCI_SLOT_NAME": ""}
        try:
            with open(f"/sys/class/drm/{self.card}/device/uevent", encoding="utf-8") as card_uevent:
                content = card_uevent.readlines()
        except FileNotFoundError:
            logger.error("Unable to read driver information for card %s", self.card)
            raise
        for line in content:
            key, value = line.split("=", 1)
            infos[key] = value.strip()
        return infos

    def get_vulkaninfo(self) -> Dict[str, Dict[str, str]]:
        """Runs vulkaninfo to find the GPU name"""
        subprocess_env = dict(os.environ)
        subprocess_env["VK_DRIVER_FILES"] = self.icd_files  # Currently supported
        subprocess_env["VK_ICD_FILENAMES"] = self.icd_files  # Deprecated
        vulkaninfo_output = system.read_process_output(
            ["vulkaninfo", "--summary"], env=subprocess_env, error_result=None
        ).split("\n")
        result = {}
        devices_seen = False
        for line in vulkaninfo_output:
            line = line.strip()
            if not line or line.startswith("==="):
                continue
            if line == "Devices:":
                devices_seen = True
                continue
            if not devices_seen:
                continue
            if line.startswith("GPU"):
                current_gpu = line
                result[current_gpu] = {}
            else:
                key, value = line.split("= ", maxsplit=1)
                result[current_gpu][key.strip()] = value.strip()
        if "Failed to detect any valid GPUs" in result or "ERROR: [Loader Message]" in result:
            logger.warning("Vulkan failed to detect any GPUs: %s", result)
            return {}
        return result

    def get_vulkaninfo_name(self) -> Optional[str]:
        vulkaninfo = self.get_vulkaninfo()
        for gpu_index in vulkaninfo:
            pci_id = "%s:%s" % (
                vulkaninfo[gpu_index]["vendorID"].replace("0x", ""),
                vulkaninfo[gpu_index]["deviceID"].replace("0x", ""),
            )
            if pci_id == self.pci_id:
                return vulkaninfo[gpu_index]["deviceName"]
        return None

    def get_lspci_name(self):
        lspci_results = [line.split(maxsplit=1) for line in system.execute(["lspci"], timeout=3).split("\n")]
        lspci_results = [parts for parts in lspci_results if len(parts) == 2 and ": " in parts[1]]
        devices = [(pci_id, device_desc.split(": ")[1]) for pci_id, device_desc in lspci_results]
        for device in devices:
            if f"0000:{device[0]}" == self.pci_slot:
                return device[1]
        return "No GPU"

    def get_icd_files(self):
        loader = self.driver
        loader_map = {
            "amdgpu": "radeon",
            "vc4-drm": "broadcom",
            "v3d": "broadcom",
            "virtio-pci": "lvp",
            "i915": "intel",
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
